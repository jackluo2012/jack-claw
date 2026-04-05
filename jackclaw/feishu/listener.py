"""
飞书 WebSocket 监听

监听飞书事件，转换为 InboundMessage
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Callable

from lark_oapi.ws import Client as WsClient, Event

from jackclaw.models import InboundMessage, Attachment
from jackclaw.feishu.session_key import build_routing_key, RoutingType

if TYPE_CHECKING:
    from lark_oapi.client import Client

logger = logging.getLogger(__name__)

OnMessageCallback = Callable[[InboundMessage], None]


class FeishuListener:
    """飞书 WebSocket 监听器"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        on_message: OnMessageCallback,
        loop: asyncio.AbstractEventLoop | None = None,
        allowed_chats: list[str] | None = None,
    ):
        self._app_id = app_id
        self._app_secret = app_secret
        self._on_message = on_message
        self._loop = loop or asyncio.get_running_loop()
        self._allowed_chats = set(allowed_chats) if allowed_chats else None
        self._ws_client: WsClient | None = None

    async def start(self) -> None:
        """启动 WebSocket 连接"""
        self._ws_client = WsClient(
            app_id=self._app_id,
            app_secret=self._app_secret,
        )
        self._ws_client.on_message(self._handle_event)
        await self._ws_client.start()

    async def stop(self) -> None:
        """停止 WebSocket 连接"""
        if self._ws_client:
            await self._ws_client.stop()

    def _handle_event(self, event: Event) -> None:
        """处理飞书事件"""
        try:
            if event.header.event_type == "im.message.receive_v1":
                self._handle_message_event(event)
        except Exception:
            logger.exception("Failed to handle event")

    def _handle_message_event(self, event: Event) -> None:
        """处理消息事件"""
        message = event.message
        sender = event.sender

        chat_id = message.chat_id
        if self._allowed_chats and chat_id not in self._allowed_chats:
            return

        chat_type = message.chat_type
        if chat_type == "p2p":
            routing_key = build_routing_key(RoutingType.P2P, open_id=sender.sender_id.open_id)
            root_id = ""
        elif chat_type == "group":
            routing_key = build_routing_key(RoutingType.GROUP, chat_id=chat_id)
            root_id = ""
        else:
            root_id = message.root_id
            routing_key = build_routing_key(RoutingType.THREAD, chat_id=chat_id, thread_id=root_id)

        content = self._parse_content(message)
        attachment = self._parse_attachment(message)

        inbound = InboundMessage(
            routing_key=routing_key,
            content=content,
            msg_id=message.message_id,
            root_id=root_id,
            sender_id=sender.sender_id.open_id,
            ts=int(message.create_time),
            attachment=attachment,
        )

        self._loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self._async_callback(inbound))
        )

    async def _async_callback(self, inbound: InboundMessage) -> None:
        try:
            if asyncio.iscoroutinefunction(self._on_message):
                await self._on_message(inbound)
            else:
                self._on_message(inbound)
        except Exception:
            logger.exception("on_message callback error")

    def _parse_content(self, message) -> str:
        """解析消息内容"""
        msg_type = message.message_type
        content = message.content
        if msg_type == "text":
            try:
                data = json.loads(content)
                return data.get("text", "")
            except Exception:
                return ""
        return ""

    def _parse_attachment(self, message) -> Attachment | None:
        """解析附件"""
        msg_type = message.message_type
        content = message.content
        if msg_type in ("image", "file"):
            try:
                data = json.loads(content)
                file_key = data.get("file_key", "") or data.get("image_key", "")
                file_name = data.get("file_name", "") or f"{file_key}.jpg"
                return Attachment(msg_type=msg_type, file_key=file_key, file_name=file_name)
            except Exception:
                return None
        return None


async def run_forever(listener: FeishuListener) -> None:
    """运行监听器直到停止"""
    await listener.start()
    try:
        await asyncio.Event().wait()
    finally:
        await listener.stop()
