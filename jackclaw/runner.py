"""
Runner — 执行引擎

核心职责：
- 维护 per-routing_key 的消息队列，保证同一会话的消息串行处理
- 拦截和处理 Slash Command（/new, /help, /status 等）
- 调用 Agent 生成回复
- 处理异常并发送错误消息

架构：

    FeishuListener --> dispatch() --> Queue[routing_key]
                                           |
                                           v
                                      _worker()
                                           |
                      +--------------------+--------------------+
                      |                    |                    |
                      v                    v                    v
                 Slash Command      Agent Processing     Error Handling
                      |                    |                    |
                      v                    v                    v
                  直接回复            Session 保存          发送错误消息

消息处理流程：
1. 消息入队（dispatch）：根据 routing_key 分发到对应队列
2. 队列消费（_worker）：串行处理队列中的消息
3. Slash 命令处理（_handle_slash）：拦截并直接回复
4. Agent 调用（_handle）：调用 agent_fn 生成回复
5. 结果发送：保存历史并发送回复

注意：
- 每个 routing_key 有独立的队列和 worker
- worker 空闲超时后自动清理（默认 300 秒）
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from jackclaw.models import InboundMessage, SenderProtocol
from jackclaw.session.manager import SessionManager
from jackclaw.session.models import MessageEntry

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Agent 函数类型：接收消息和历史，返回回复
AgentFn = Callable[
    [str, list[MessageEntry], str, str, str, bool],  # user_message, history, session_id, routing_key, root_id, verbose
    Awaitable[str],  # reply
]

# 帮助文本
_HELP_TEXT = """\
可用命令：
/new — 创建新对话
/verbose on|off — 开启/关闭详细模式
/status — 查看当前对话信息
/help — 显示本帮助"""

# 支持的 Slash 命令集合
_SLASH_COMMANDS = frozenset({"/new", "/verbose", "/help", "/status"})


class Runner:
    """
    执行引擎
    
    管理消息队列和 worker，协调消息处理流程。
    
    使用方式：
        runner = Runner(
            session_mgr=session_manager,
            sender=feishu_sender,
            agent_fn=agent.run,
            idle_timeout=300.0,
        )
        
        # 消息入队
        await runner.dispatch(inbound_message)
        
        # 关闭
        await runner.shutdown()
    """

    def __init__(
        self,
        session_mgr: SessionManager,
        sender: SenderProtocol,
        agent_fn: AgentFn | None = None,
        idle_timeout: float = 300.0,
    ):
        """
        初始化 Runner
        
        Args:
            session_mgr: Session 管理器
            sender: 消息发送器
            agent_fn: Agent 处理函数，None 则使用默认占位回复
            idle_timeout: 队列空闲超时时间（秒），超时后清理队列
        """
        self._session_mgr = session_mgr
        self._sender = sender
        self._agent_fn = agent_fn or self._default_agent_fn
        self._idle_timeout = idle_timeout
        self._queues: dict[str, asyncio.Queue[InboundMessage]] = {}
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._dispatch_lock = asyncio.Lock()

    async def dispatch(self, inbound: InboundMessage) -> None:
        """
        消息入队
        
        根据 routing_key 分发到对应队列。如果队列不存在，则创建新的 worker。
        
        Args:
            inbound: 入站消息
        """
        key = inbound.routing_key
        async with self._dispatch_lock:
            if key not in self._queues:
                self._queues[key] = asyncio.Queue()
                self._workers[key] = asyncio.create_task(self._worker(key))
                logger.debug("Created new worker for routing_key: %s", key)
        await self._queues[key].put(inbound)

    async def shutdown(self) -> None:
        """
        关闭所有 worker
        
        取消所有正在运行的任务并清理资源。
        """
        for task in list(self._workers.values()):
            task.cancel()
        if self._workers:
            await asyncio.gather(*self._workers.values(), return_exceptions=True)
        self._workers.clear()
        self._queues.clear()
        logger.info("Runner shutdown complete")

    async def _worker(self, key: str) -> None:
        """
        队列消费者
        
        串行处理队列中的消息，空闲超时后自动退出。
        
        Args:
            key: routing_key
        """
        queue = self._queues[key]
        while True:
            try:
                # 等待消息，超时则退出
                inbound = await asyncio.wait_for(queue.get(), timeout=self._idle_timeout)
            except asyncio.TimeoutError:
                # 空闲超时，清理队列
                async with self._dispatch_lock:
                    if self._workers.get(key) is asyncio.current_task():
                        self._queues.pop(key, None)
                        self._workers.pop(key, None)
                        logger.debug("Worker timeout, cleaned up: %s", key)
                return

            try:
                await self._handle(inbound)
            except Exception:
                logger.exception("[%s] handle error", key)
                try:
                    await self._sender.send_text(key, "处理出错，请稍后重试。", inbound.root_id)
                except Exception:
                    logger.exception("[%s] send error", key)
            finally:
                queue.task_done()

    async def _handle(self, inbound: InboundMessage) -> None:
        """
        处理单条消息
        
        流程：
        1. 检查是否为 Slash 命令
        2. 如果是，直接回复命令结果
        3. 如果不是，调用 Agent 生成回复
        4. 保存对话历史
        5. 发送回复
        
        Args:
            inbound: 入站消息
        """
        key = inbound.routing_key

        # 检查 Slash 命令
        slash_reply = await self._handle_slash(inbound)
        if slash_reply is not None:
            await self._sender.send_text(key, slash_reply, inbound.root_id)
            return

        # 获取或创建 Session
        session = await self._session_mgr.get_or_create(key)
        history = await self._session_mgr.load_history(session.id)

        # 调用 Agent
        reply = await self._agent_fn(
            inbound.content,
            history,
            session.id,
            inbound.routing_key,
            inbound.root_id,
            session.verbose,
        )

        # 保存历史
        await self._session_mgr.append(
            session.id,
            user=inbound.content,
            assistant=reply,
            feishu_msg_id=inbound.msg_id,
        )

        # 发送回复
        await self._sender.send(key, reply, inbound.root_id)

    async def _handle_slash(self, inbound: InboundMessage) -> str | None:
        """
        处理 Slash 命令
        
        支持的命令：
        - /new: 创建新对话
        - /verbose on|off: 切换详细模式
        - /help: 显示帮助
        - /status: 显示当前对话状态
        
        Args:
            inbound: 入站消息
            
        Returns:
            命令回复，如果不是命令则返回 None
        """
        text = inbound.content.strip()
        if not text.startswith("/"):
            return None

        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip().lower() if len(parts) > 1 else ""

        if cmd not in _SLASH_COMMANDS:
            return None

        key = inbound.routing_key

        if cmd == "/new":
            new_session = await self._session_mgr.create_new_session(key)
            return f"已创建新对话 {new_session.id}"

        if cmd == "/verbose":
            if arg == "on":
                await self._session_mgr.update_verbose(key, True)
                return "详细模式已开启。"
            if arg == "off":
                await self._session_mgr.update_verbose(key, False)
                return "详细模式已关闭。"
            session = await self._session_mgr.get_or_create(key)
            status = "开启" if session.verbose else "关闭"
            return f"当前详细模式：{status}"

        if cmd == "/help":
            return _HELP_TEXT

        if cmd == "/status":
            session = await self._session_mgr.get_or_create(key)
            return f"当前对话：{session.id}，消息数：{session.message_count}"

        return None

    @staticmethod
    async def _default_agent_fn(
        user_message: str,
        history: list[MessageEntry],
        session_id: str = "",
        routing_key: str = "",
        root_id: str = "",
        verbose: bool = False,
    ) -> str:
        """
        默认 Agent 函数
        
        在没有提供 agent_fn 时使用，返回占位回复。
        
        Args:
            user_message: 用户消息
            history: 对话历史
            session_id: 会话 ID
            routing_key: 路由键
            root_id: 话题根消息 ID
            verbose: 是否详细模式
            
        Returns:
            占位回复
        """
        return "Phase 1 骨架已就绪。"
