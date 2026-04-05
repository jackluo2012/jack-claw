"""
飞书消息发送

支持：
- 单聊：CreateMessage API
- 群聊：CreateMessage API
- 话题：ReplyMessage API
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from jackclaw.feishu.session_key import parse_routing_key, RoutingType

if TYPE_CHECKING:
    from lark_oapi.client import Client

logger = logging.getLogger(__name__)


class FeishuSender:
    """飞书消息发送器"""

    def __init__(self, client: "Client"):
        self._client = client

    async def send(self, routing_key: str, content: str, root_id: str = "") -> None:
        """发送消息"""
        routing = parse_routing_key(routing_key)
        if routing.type == RoutingType.THREAD and root_id:
            await self._reply_in_thread(root_id, content)
        else:
            await self._create_message(routing, content)

    async def send_text(self, routing_key: str, content: str, root_id: str = "") -> None:
        """发送纯文本消息"""
        await self.send(routing_key, content, root_id)

    async def _create_message(self, routing, content: str) -> None:
        """CreateMessage API"""
        from lark_oapi.api.im.v1 import CreateMessageRequestBody, CreateMessageRequest

        receive_id = routing.open_id if routing.type == RoutingType.P2P else routing.chat_id
        receive_id_type = "open_id" if routing.type == RoutingType.P2P else "chat_id"

        body = CreateMessageRequestBody.builder() \
            .receive_id(receive_id) \
            .msg_type("text") \
            .content(f'{{"text":"{content}"}}') \
            .uuid(str(uuid.uuid4())) \
            .build()

        request = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(body) \
            .build()

        try:
            response = self._client.im.v1.message.acreate(request)
            if not response.success():
                logger.warning("CreateMessage failed: %s", response.msg)
        except Exception:
            logger.exception("CreateMessage error")

    async def _reply_in_thread(self, root_id: str, content: str) -> None:
        """ReplyMessage API"""
        from lark_oapi.api.im.v1 import ReplyMessageRequestBody, ReplyMessageRequest

        body = ReplyMessageRequestBody.builder() \
            .msg_type("text") \
            .content(f'{{"text":"{content}"}}') \
            .uuid(str(uuid.uuid4())) \
            .build()

        request = ReplyMessageRequest.builder() \
            .message_id(root_id) \
            .request_body(body) \
            .build()

        try:
            response = self._client.im.v1.message.areply(request)
            if not response.success():
                logger.warning("ReplyMessage failed: %s", response.msg)
        except Exception:
            logger.exception("ReplyMessage error")
