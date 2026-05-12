"""
runner.py — 29 课 Runner（团队多 Agent 路由扩展）
routing_key 分派 + wake 去重
在 22 课 Runner 基础上扩展：
- `team:{role}` routing_key 路由到对应角色 agent_fn（agent_fn_map）
- `p2p:{open_id}` 原样路由到 Manager
- wake_reason meta 去重（避免 at cron + heartbeat 同时触发多跑）

对齐 DESIGN.md §5.3 / §13.3。
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from jackclaw_team.models import InboundMessage, SenderProtocol
from jackclaw_team.session.manager import SessionManager
from jackclaw_team.session.models import SessionEntry
from jackclaw_team.observability.metrics import (
    record_error,
    record_inbound_message,
    runner_queue_size,
    runner_workers_active,
)


if TYPE_CHECKING:
    from jackclaw_team.feishu.downloader import FeishuDownloader

logger = logging.getLogger(__name__)    

AgentFn = Callable[..., Awaitable[str]]

_SLASH_COMMANDS = frozenset({"/new", "/verbose", "/help", "/status"})
_HELP_TEXT = """可用命令：
/new — 创建新对话
/verbose on|off — 开启/关闭详细模式
/status — 查看当前对话信息
/help — 显示本帮助"""

# 29 课新增：routing_key 前缀
TEAM_PREFIX = "team:"
P2P_PREFIX = "p2p:"

def _pick_agent_fn(
    routing_key: str,  # 路由键，用于确定选择哪个代理函数
    agent_fn_map: dict[str, AgentFn] | None,  # 代理函数映射字典，键为角色名，值为对应的代理函数
    default_fn: AgentFn | None,  # 默认的代理函数，当没有匹配到特定角色时使用
) -> AgentFn:  # 返回一个代理函数
    """按 routing_key 选对应角色的 agent_fn。

    - team:{role} → agent_fn_map[role]
    - p2p:* / group:* / thread:* → agent_fn_map["manager"] 或 default_fn
    """
    if agent_fn_map:  # 检查代理函数映射字典是否存在
        if routing_key.startswith(TEAM_PREFIX):  # 检查路由键是否以"team:"开头
            role = routing_key[len(TEAM_PREFIX):]  # 提取角色名
            if role in agent_fn_map:  # 检查角色是否在代理函数映射中
                return agent_fn_map[role]  # 返回对应角色的代理函数
            raise ValueError(f"no agent_fn for team role: {role}")  # 如果角色不存在，抛出异常
        # 飞书通道：固定找 manager
        if "manager" in agent_fn_map:  # 检查manager角色是否在代理函数映射中
            return agent_fn_map["manager"]  # 返回manager角色的代理函数
    if default_fn is not None:  # 检查是否存在默认代理函数
        return default_fn  # 返回默认代理函数
    raise RuntimeError("no agent_fn available for routing_key: " + routing_key)  # 如果没有可用的代理函数，抛出异常


class Runner:
    """执行引擎：per-routing_key 串行队列 + Slash Command + Agent 调度 + team 路由."""

    def __init__(
        self,
        session_mgr: SessionManager,  # 会话管理器：负责管理用户会话
        sender: SenderProtocol,       # 发送协议实现：负责消息发送
        *,
        agent_fn: AgentFn | None = None,  # 单个 agent 函数（22课兼容）：用于处理消息的函数
        agent_fn_map: dict[str, AgentFn] | None = None,  # 多角色 agent 函数映射（29课）：不同角色对应不同的处理函数
        idle_timeout: float = 300.0,  # 空闲超时时间（秒）：会话空闲多久后超时
        downloader: "FeishuDownloader | None" = None,  # 飞书下载器：用于下载飞书资源
    ) -> None:
        """初始化执行器，设置会话管理器、发送器、agent函数等核心组件."""
        self._session_mgr = session_mgr            # 会话管理器实例
        self._sender = sender                      # 发送器实例
        self._agent_fn = agent_fn            # 22 课兼容：单 agent_fn
        self._agent_fn_map = agent_fn_map    # 29 课：多角色
        self._idle_timeout = idle_timeout
        self._downloader = downloader
        self._queues: dict[str, asyncio.Queue[InboundMessage]] = {}
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._dispatch_lock = asyncio.Lock()

    async def dispatch(self, inbound: InboundMessage) -> None:
        """入口：按 routing_key 入对应串行队列，启动 worker（空闲会自动退出）."""
        # 29 课：wake_reason 去重（相同 routing_key 已有 pending wake 则丢弃本次）
        if _is_wake_message(inbound) and self._has_pending_wake(inbound.routing_key):
            logger.debug("dedup wake: routing_key=%s", inbound.routing_key)
            return

        record_inbound_message(inbound.routing_key, has_attachment=inbound.attachment is not None)  # 记录入站消息信息，包括是否有附件
        async with self._dispatch_lock:  # 使用异步锁确保线程安全
            queue = self._queues.get(inbound.routing_key)  # 获取对应 routing_key 的队列
            if queue is None:  # 如果队列不存在，则创建新队列
                queue = asyncio.Queue()
                self._queues[inbound.routing_key] = queue
            queue.put_nowait(inbound)  # 将消息非阻塞地放入队列
            rk_type = _rk_type(inbound.routing_key)  # 获取路由键类型
            runner_queue_size.labels(routing_key_type=rk_type).set(queue.qsize())  # 更新队列大小指标
            if (worker := self._workers.get(inbound.routing_key)) is None or worker.done():  # 检查 worker 是否不存在或已完成
                self._workers[inbound.routing_key] = asyncio.create_task(  # 创建新的 worker 任务
                    self._worker(inbound.routing_key, queue)
                )
                runner_workers_active.labels(routing_key_type=rk_type).inc()  # 更新活跃 worker 数量指标

    def _has_pending_wake(self, routing_key: str) -> bool:
        # 获取与指定路由键关联的队列
        q = self._queues.get(routing_key)
        # 如果队列不存在，则返回False
        if q is None:
            return False
        # 遍历队列中的所有待处理元素（注意：这里使用了内部API _queue）
        # asyncio.Queue 内部 deque _queue 可访问（私有 API，但广泛使用）
        for pending in list(q._queue):  # type: ignore[attr-defined]
            # 获取待处理元素的meta属性
            meta = getattr(pending, "meta", None)
            # 检查meta是否存在且包含特定的唤醒原因（new_mail或heartbeat）
            if meta and meta.get("wake_reason") in {"new_mail", "heartbeat"}:
                return True
        # 如果没有找到符合条件的待处理元素，返回False
        return False

    async def _worker(self, routing_key: str, queue: asyncio.Queue[InboundMessage]) -> None:
        try:
            # 无限循环处理队列中的消息
            while True:
                try:
                    # 从队列中获取消息，设置超时时间
                    inbound = await asyncio.wait_for(queue.get(), timeout=self._idle_timeout)
                except asyncio.TimeoutError:
                    # 如果获取消息超时，则退出循环
                    break
                try:
                    # 处理获取到的消息
                    await self._handle(inbound)
                except Exception as exc:
                    # 捕获并记录处理消息时的异常
                    logger.exception("worker handle error: %s", exc)
                    record_error(component="runner", error_type=type(exc).__name__)
                finally:
                    # 更新队列大小的监控指标
                    runner_queue_size.labels(routing_key_type=_rk_type(routing_key)).set(queue.qsize())
        finally:
            # 确保在worker退出时执行清理工作
            async with self._dispatch_lock:
                # 从活跃worker集合中移除当前worker
                self._workers.pop(routing_key, None)
                # 减少活跃worker的监控计数
                runner_workers_active.labels(routing_key_type=_rk_type(routing_key)).dec()

    async def _handle(self, inbound: InboundMessage) -> None:
        """核心处理：slash 拦截 / session / 调 agent_fn / 回发送."""
        # Slash 拦截
        txt = (inbound.content or "").strip()
        if txt in _SLASH_COMMANDS or txt.startswith("/verbose "):
            reply = await self._handle_slash(inbound, txt)
            await self._send_reply(inbound, reply)
            return

        # session
        session = await self._session_mgr.get_or_create(inbound.routing_key)
        session_id = session.id
        history = await self._session_mgr.load_history(session_id)

        # 选 agent_fn
        agent_fn = _pick_agent_fn(inbound.routing_key, self._agent_fn_map, self._agent_fn)
        verbose = session.verbose

        # kickoff
        reply = await agent_fn(
            inbound.content,
            history,
            session_id,
            inbound.routing_key,
            getattr(inbound, "root_id", ""),
            verbose,
        )

        # persist
        await self._session_mgr.append(
            session_id,
            user=inbound.content,
            feishu_msg_id=inbound.msg_id,
            assistant=reply,
        )

        # 回消息（p2p 走飞书；team:* wake 不回）
        if not inbound.routing_key.startswith(TEAM_PREFIX):
            await self._send_reply(inbound, reply)

    async def _handle_slash(self, inbound: InboundMessage, text: str) -> str:
        if text == "/new":
            await self._session_mgr.create_new_session(inbound.routing_key)
            return "已创建新对话，之前的历史不会带入。"
        if text == "/help":
            return _HELP_TEXT
        if text == "/status":
            session = await self._session_mgr.get_or_create(inbound.routing_key)
            return f"当前 session: {session.id[:8]}"
        if text.startswith("/verbose"):
            parts = text.split()
            session = await self._session_mgr.get_or_create(inbound.routing_key)
            if len(parts) == 1:
                return f"当前详细模式：{'开启' if session.verbose else '关闭'}"
            val = parts[1].lower() == "on"
            await self._session_mgr.update_verbose(inbound.routing_key, val)
            return f"✅ 详细模式已{'开启' if val else '关闭'}。"
        return _HELP_TEXT

    async def _send_reply(self, inbound: InboundMessage, reply: str) -> None:
        """调用 sender 发消息；失败只记日志，不抛."""
        try:
            await self._sender.send(inbound.routing_key, reply,
                                     root_id=getattr(inbound, "root_id", ""))
        except Exception as exc:
            logger.exception("send reply failed: %s", exc)
            record_error(component="sender", error_type=type(exc).__name__)


def _rk_type(routing_key: str) -> str:
    if routing_key.startswith(P2P_PREFIX):
        return "p2p"
    if routing_key.startswith("group:"):
        return "group"
    if routing_key.startswith("thread:"):
        return "thread"
    if routing_key.startswith(TEAM_PREFIX):
        return "team"
    return "unknown"


def _is_wake_message(inbound: InboundMessage) -> bool:
    meta = getattr(inbound, "meta", None)
    return bool(meta and meta.get("wake_reason"))