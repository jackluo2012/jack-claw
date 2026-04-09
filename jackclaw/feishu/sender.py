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

    async def send_thinking(self, routing_key: str, root_id: str = "") -> str:
        """发送正在思考的提示卡片，返回卡片消息ID - 使用最新的飞书卡片API"""
        from lark_oapi.api.im.v1 import CreateMessageRequestBody, CreateMessageRequest

        routing = parse_routing_key(routing_key)

        # 如果在话题中，先回复一条消息
        if routing.type == RoutingType.THREAD and root_id:
            # 在话题中回复，获取消息ID
            await self._reply_in_thread(root_id, "正在思考中...")
            # 由于话题回复API不返回消息ID，返回空字符串表示降级模式
            return ""

        receive_id = routing.open_id if routing.type == RoutingType.P2P else routing.chat_id
        receive_id_type = "open_id" if routing.type == RoutingType.P2P else "chat_id"

        # 创建一个简单的加载卡片 - 使用最新的飞书卡片格式
        card_content = {
            "config": {"wide_screen_mode": True},
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": "🤔 正在思考中...",
                        "tag": "lark_md"
                    }
                }
            ]
        }

        import json
        body = CreateMessageRequestBody.builder() \
            .receive_id(receive_id) \
            .msg_type("interactive") \
            .content(json.dumps(card_content, ensure_ascii=False)) \
            .uuid(str(uuid.uuid4())) \
            .build()

        request = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(body) \
            .build()

        try:
            response = await self._client.im.v1.message.acreate(request)
            if response.success() and response.data:
                logger.debug("Thinking card created: %s", response.data.message_id)
                return response.data.message_id
            else:
                logger.warning("CreateMessage (thinking card) failed: code=%s, msg=%s", response.code, response.msg)
                return ""
        except Exception as e:
            logger.exception("CreateMessage (thinking card) error: %s", str(e))
            return ""

    async def delete_message(self, message_id: str) -> None:
        """删除消息 - 使用最新的飞书消息删除API"""
        from lark_oapi.api.im.v1 import DeleteMessageRequest

        try:
            delete_request = DeleteMessageRequest.builder() \
                .message_id(message_id) \
                .build()

            delete_response = await self._client.im.v1.message.adelete(delete_request)
            if not delete_response.success():
                logger.warning("DeleteMessage failed: code=%s, msg=%s", delete_response.code, delete_response.msg)
            else:
                logger.debug("Deleted message successfully: %s", message_id)
        except Exception as e:
            logger.exception("DeleteMessage error: %s", str(e))

    async def update_card(self, card_msg_id: str, content: str) -> None:
        """更新卡片内容 - 已废弃，保留兼容性"""
        # Feishu 不支持将 interactive 卡片更新为文本消息
        # 此方法已废弃，使用 delete_message + send 组合代替
        await self.delete_message(card_msg_id)

    async def _create_message(self, routing, content: str) -> None:
        """CreateMessage API - 使用最新的飞书消息发送API"""
        from lark_oapi.api.im.v1 import CreateMessageRequestBody, CreateMessageRequest

        receive_id = routing.open_id if routing.type == RoutingType.P2P else routing.chat_id
        receive_id_type = "open_id" if routing.type == RoutingType.P2P else "chat_id"

        # 转义JSON字符串中的特殊字符
        import json
        safe_content = json.dumps(content)[1:-1]  # 移除外层引号

        body = CreateMessageRequestBody.builder() \
            .receive_id(receive_id) \
            .msg_type("text") \
            .content(f'{{"text":"{safe_content}"}}') \
            .uuid(str(uuid.uuid4())) \
            .build()

        request = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(body) \
            .build()

        try:
            response = await self._client.im.v1.message.acreate(request)
            if not response.success():
                logger.warning("CreateMessage failed: code=%s, msg=%s", response.code, response.msg)
            else:
                logger.debug("CreateMessage succeeded: message_id=%s", response.data.message_id if response.data else "N/A")
        except Exception as e:
            logger.exception("CreateMessage error: %s", str(e))

    async def _reply_in_thread(self, root_id: str, content: str) -> None:
        """ReplyMessage API - 使用最新的飞书话题回复API"""
        from lark_oapi.api.im.v1 import ReplyMessageRequestBody, ReplyMessageRequest

        # 转义JSON字符串中的特殊字符
        import json
        safe_content = json.dumps(content)[1:-1]  # 移除外层引号

        body = ReplyMessageRequestBody.builder() \
            .msg_type("text") \
            .content(f'{{"text":"{safe_content}"}}') \
            .uuid(str(uuid.uuid4())) \
            .build()

        request = ReplyMessageRequest.builder() \
            .message_id(root_id) \
            .request_body(body) \
            .build()

        try:
            response = await self._client.im.v1.message.areply(request)
            if not response.success():
                logger.warning("ReplyMessage failed: code=%s, msg=%s", response.code, response.msg)
            else:
                logger.debug("ReplyMessage succeeded: message_id=%s", response.data.message_id if response.data else "N/A")
        except Exception as e:
            logger.exception("ReplyMessage error: %s", str(e))
