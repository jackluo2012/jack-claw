"""
飞书 WebSocket 监听

监听飞书事件，转换为 InboundMessage
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Callable

from lark_oapi.ws import Client as WsClient
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1

from jackclaw.models import InboundMessage, Attachment
from jackclaw.feishu.session_key import build_routing_key, RoutingType

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
        self._loop = loop
        self._allowed_chats = set(allowed_chats) if allowed_chats else None
        self._ws_client: WsClient | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """启动 WebSocket 连接（在独立线程中运行）"""
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        def noop_handler(event):
            pass

        event_handler = (
            EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_message_event)
            .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(noop_handler)
            .register_p2_customized_event("p2p_chat_create", noop_handler)
            .build()
        )
        self._ws_client = WsClient(
            app_id=self._app_id,
            app_secret=self._app_secret,
            event_handler=event_handler,
        )

        self._thread = threading.Thread(target=self._run_ws_client, daemon=True)
        self._thread.start()

    def _run_ws_client(self) -> None:
        """在独立线程中运行 WebSocket 客户端"""
        try:
            self._ws_client.start()
        except Exception as e:
            logger.exception("WebSocket client error: %s", e)

    def stop(self) -> None:
        """停止 WebSocket 连接"""
        self._stop_event.set()
        # SDK 的 stop 方法需要在 WS 线程中调用，这里用超时等待
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _handle_message_event(self, event: P2ImMessageReceiveV1) -> None:
        """处理消息事件"""
        try:
            message = event.event.message
            sender = event.event.sender

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
                root_id = message.root_id or ""
                routing_key = build_routing_key(RoutingType.THREAD, chat_id=chat_id, thread_id=root_id)

            content = self._parse_content(message)
            attachment = self._parse_attachment(message)

            inbound = InboundMessage(
                routing_key=routing_key,
                content=content,
                msg_id=message.message_id,
                root_id=root_id,
                sender_id=sender.sender_id.open_id,
                ts=int(message.create_time) if message.create_time else 0,
                attachment=attachment,
            )

            # 从 WS 线程回调到主事件循环
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._async_callback(inbound))
            )
        except Exception:
            logger.exception("Failed to handle message event")

    async def _async_callback(self, inbound: InboundMessage) -> None:
        """异步回调"""
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
        if msg_type == "text" and content:
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
        if msg_type in ("image", "file") and content:
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
    listener.start()
    try:
        await asyncio.Event().wait()
    finally:
        listener.stop()
