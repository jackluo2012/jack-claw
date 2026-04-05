"""
Runner — 执行引擎

核心职责：
- per-routing_key 串行队列
- Slash Command 拦截
- Agent 调度
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

AgentFn = Callable[[str, list[MessageEntry], str, str, str, bool], Awaitable[str]]

_HELP_TEXT = """\
可用命令：
/new — 创建新对话
/verbose on|off — 开启/关闭详细模式
/status — 查看当前对话信息
/help — 显示本帮助"""

_SLASH_COMMANDS = frozenset({"/new", "/verbose", "/help", "/status"})


class Runner:
    """执行引擎"""

    def __init__(
        self,
        session_mgr: SessionManager,
        sender: SenderProtocol,
        agent_fn: AgentFn | None = None,
        idle_timeout: float = 300.0,
    ):
        self._session_mgr = session_mgr
        self._sender = sender
        self._agent_fn = agent_fn or self._default_agent_fn
        self._idle_timeout = idle_timeout
        self._queues: dict[str, asyncio.Queue[InboundMessage]] = {}
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._dispatch_lock = asyncio.Lock()

    async def dispatch(self, inbound: InboundMessage) -> None:
        """消息入队"""
        key = inbound.routing_key
        async with self._dispatch_lock:
            if key not in self._queues:
                self._queues[key] = asyncio.Queue()
                self._workers[key] = asyncio.create_task(self._worker(key))
        await self._queues[key].put(inbound)

    async def shutdown(self) -> None:
        """取消所有 worker"""
        for task in list(self._workers.values()):
            task.cancel()
        if self._workers:
            await asyncio.gather(*self._workers.values(), return_exceptions=True)
        self._workers.clear()
        self._queues.clear()

    async def _worker(self, key: str) -> None:
        """per-routing_key worker"""
        queue = self._queues[key]
        while True:
            try:
                inbound = await asyncio.wait_for(queue.get(), timeout=self._idle_timeout)
            except asyncio.TimeoutError:
                async with self._dispatch_lock:
                    if self._workers.get(key) is asyncio.current_task():
                        self._queues.pop(key, None)
                        self._workers.pop(key, None)
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
        """处理单条消息"""
        key = inbound.routing_key
        slash_reply = await self._handle_slash(inbound)
        if slash_reply is not None:
            await self._sender.send_text(key, slash_reply, inbound.root_id)
            return
        session = await self._session_mgr.get_or_create(key)
        history = await self._session_mgr.load_history(session.id)
        reply = await self._agent_fn(inbound.content, history, session.id, inbound.routing_key, inbound.root_id, session.verbose)
        await self._session_mgr.append(session.id, user=inbound.content, assistant=reply, feishu_msg_id=inbound.msg_id)
        await self._sender.send(key, reply, inbound.root_id)

    async def _handle_slash(self, inbound: InboundMessage) -> str | None:
        """处理 slash command"""
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
        """默认 agent（Phase 1: 固定回复）"""
        return "Phase 1 骨架已就绪。"
