"""
飞书 WebSocket 监听器

监听飞书实时事件，将消息转换为标准化的 InboundMessage 对象。

核心功能：
- WebSocket 长连接管理
- 事件类型分发
- 消息内容解析（文本、图片、文件）
- 线程安全的异步回调

依赖：
- lark_oapi>=1.5.3（飞书官方 Python SDK）

注意：
- SDK 的 WsClient.start() 是同步阻塞方法，内部管理自己的事件循环
- 因此在独立线程中运行 WebSocket 客户端
- 通过 call_soon_threadsafe 将事件回调到主事件循环
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

# 消息回调类型：接收 InboundMessage，无返回值
OnMessageCallback = Callable[[InboundMessage], None]


class FeishuListener:
    """
    飞书 WebSocket 监听器
    
    负责建立与飞书服务器的 WebSocket 长连接，接收实时消息事件，
    并将其转换为标准化的 InboundMessage 对象后回调给上层处理。
    
    使用方式：
        listener = FeishuListener(
            app_id="cli_xxx",
            app_secret="xxx",
            on_message=handle_message,
            allowed_chats=["oc_xxx"],  # 可选，白名单
        )
        listener.start()  # 非阻塞，在后台线程运行
        
    线程模型：
        - WebSocket 客户端在独立线程中运行（因为 SDK 的 start() 是阻塞的）
        - 消息回调通过 call_soon_threadsafe 投递到主事件循环
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        on_message: OnMessageCallback,
        loop: asyncio.AbstractEventLoop | None = None,
        allowed_chats: list[str] | None = None,
    ):
        """
        初始化监听器
        
        Args:
            app_id: 飞书应用 ID
            app_secret: 飞书应用密钥
            on_message: 消息回调函数，接收 InboundMessage
            loop: 主事件循环（用于线程安全回调）
            allowed_chats: 允许的 chat_id 白名单，None 表示不限制
        """
        self._app_id = app_id
        self._app_secret = app_secret
        self._on_message = on_message
        self._loop = loop
        self._allowed_chats = set(allowed_chats) if allowed_chats else None
        self._ws_client: WsClient | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """
        启动 WebSocket 连接
        
        非阻塞方法，WebSocket 客户端在独立后台线程中运行。
        """
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        # 构建事件处理器
        # 使用空字符串作为 encrypt_key 和 verification_token
        # 因为 WebSocket 模式下使用 do_without_validation 跳过验证
        def noop_handler(event) -> None:
            """空处理器，用于忽略不需要的事件"""
            logger.debug(f"Noop handler called for event type: {type(event)}")

        event_handler = (
            EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_message_event)
            # 注册空处理器，避免 "processor not found" 警告
            .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(noop_handler)
            .register_p2_customized_event("p2p_chat_create", noop_handler)
            # 消息相关事件
            .register_p2_im_message_message_read_v1(noop_handler)
            .register_p2_im_message_recalled_v1(noop_handler)
            .register_p2_im_message_reaction_created_v1(noop_handler)
            .register_p2_im_message_reaction_deleted_v1(noop_handler)
            .build()
        )

        # 创建 WebSocket 客户端
        self._ws_client = WsClient(
            app_id=self._app_id,
            app_secret=self._app_secret,
            event_handler=event_handler,
        )

        # 在独立线程中启动（因为 SDK 的 start() 是阻塞的）
        self._thread = threading.Thread(target=self._run_ws_client, daemon=True, name="feishu-ws")
        self._thread.start()
        logger.info("Feishu WebSocket listener started in background thread")

    def _run_ws_client(self) -> None:
        """
        WebSocket 客户端线程入口
        
        在独立线程中运行 SDK 的阻塞式 start() 方法。
        """
        try:
            logger.info("Connecting to Feishu WebSocket...")
            self._ws_client.start()
        except Exception as e:
            logger.exception("WebSocket client error: %s", e)

    def stop(self) -> None:
        """
        停止 WebSocket 连接
        
        等待 WebSocket 线程结束（最多 5 秒）。
        """
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("WebSocket thread did not stop gracefully")
        logger.info("Feishu WebSocket listener stopped")

    def _handle_message_event(self, event: P2ImMessageReceiveV1) -> None:
        """
        处理消息接收事件
        
        将飞书的 P2ImMessageReceiveV1 事件转换为 InboundMessage，
        并通过线程安全的方式回调到主事件循环。
        
        Args:
            event: 飞书消息接收事件（SDK v1.5.3+ 格式）
        """
        logger.info(f"[FeishuListener] _handle_message_event called!")
        try:
            # SDK v1.5.3+ 的事件结构：event.event.message / event.event.sender
            message = event.event.message
            sender = event.event.sender

            logger.info(f"[FeishuListener] Message received: chat_id={message.chat_id}, "
                       f"chat_type={message.chat_type}, msg_type={message.message_type}, "
                       f"sender={sender.sender_id.open_id}")

            # 检查白名单
            chat_id = message.chat_id
            if self._allowed_chats and chat_id not in self._allowed_chats:
                logger.debug("Ignoring message from non-whitelisted chat: %s", chat_id)
                return

            # 根据聊天类型构建 routing_key
            chat_type = message.chat_type
            if chat_type == "p2p":
                # 单聊：使用发送者的 open_id
                routing_key = build_routing_key(RoutingType.P2P, open_id=sender.sender_id.open_id)
                root_id = ""
            elif chat_type == "group":
                # 群聊：使用 chat_id
                routing_key = build_routing_key(RoutingType.GROUP, chat_id=chat_id)
                root_id = ""
            else:
                # 话题：使用 chat_id + thread_id
                root_id = message.root_id or ""
                routing_key = build_routing_key(RoutingType.THREAD, chat_id=chat_id, thread_id=root_id)

            # 解析消息内容
            content = self._parse_content(message)
            attachment = self._parse_attachment(message)

            # 构建标准化消息对象
            inbound = InboundMessage(
                routing_key=routing_key,
                content=content,
                msg_id=message.message_id,
                root_id=root_id,
                sender_id=sender.sender_id.open_id,
                ts=int(message.create_time) if message.create_time else 0,
                attachment=attachment,
            )

            logger.info(f"[FeishuListener] Dispatching inbound message: routing_key={routing_key}, content={content[:50]}...")

            # 从 WebSocket 线程回调到主事件循环（线程安全）
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._async_callback(inbound))
            )
        except Exception:
            logger.exception("Failed to handle message event")

    async def _async_callback(self, inbound: InboundMessage) -> None:
        """
        异步回调包装器
        
        在主事件循环中执行用户的回调函数。
        
        Args:
            inbound: 标准化消息对象
        """
        try:
            if asyncio.iscoroutinefunction(self._on_message):
                await self._on_message(inbound)
            else:
                self._on_message(inbound)
        except Exception:
            logger.exception("on_message callback error")

    def _parse_content(self, message) -> str:
        """
        解析消息文本内容
        
        目前只处理 text 类型消息，其他类型返回空字符串。
        
        Args:
            message: 飞书消息对象
            
        Returns:
            消息文本内容
        """
        msg_type = message.message_type
        content = message.content
        if msg_type == "text" and content:
            try:
                data = json.loads(content)
                return data.get("text", "")
            except json.JSONDecodeError:
                logger.warning("Failed to parse text message content")
                return ""
        return ""

    def _parse_attachment(self, message) -> Attachment | None:
        """
        解析消息附件
        
        处理 image 和 file 类型的消息，提取文件元信息。
        
        Args:
            message: 飞书消息对象
            
        Returns:
            Attachment 对象，或 None（非附件消息）
        """
        msg_type = message.message_type
        content = message.content
        if msg_type in ("image", "file") and content:
            try:
                data = json.loads(content)
                file_key = data.get("file_key", "") or data.get("image_key", "")
                file_name = data.get("file_name", "") or f"{file_key}.{msg_type}"
                return Attachment(msg_type=msg_type, file_key=file_key, file_name=file_name)
            except json.JSONDecodeError:
                logger.warning("Failed to parse attachment content")
                return None
        return None


async def run_forever(listener: FeishuListener) -> None:
    """
    运行监听器直到停止
    
    启动监听器并保持运行，直到收到停止信号。
    
    Args:
        listener: FeishuListener 实例
    """
    # 注意：listener.start() 应该在创建 listener 后由调用者调用
    # 这里只是保持运行状态
    try:
        # 永久等待，直到被取消
        await asyncio.Event().wait()
    finally:
        listener.stop()
