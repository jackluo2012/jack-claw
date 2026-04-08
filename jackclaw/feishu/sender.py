"""
飞书消息发送器

负责通过飞书 API 发送消息，支持三种场景：
- 单聊（P2P）：使用 CreateMessage API，通过 open_id 定位接收者
- 群聊（Group）：使用 CreateMessage API，通过 chat_id 定位群组
- 话题（Thread）：使用 ReplyMessage API，回复特定消息

API 文档：
- CreateMessage: https://open.feishu.cn/document/server-docs/im-v1/message/create
- ReplyMessage: https://open.feishu.cn/document/server-docs/im-v1/message/reply

依赖：
- lark_oapi>=1.5.3（飞书官方 Python SDK）
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
    """
    飞书消息发送器
    
    封装飞书消息 API，提供统一的发送接口。
    
    使用方式：
        sender = FeishuSender(client=feishu_client)
        await sender.send("p2p:ou_xxx", "Hello!")
        await sender.send("thread:oc_xxx:ot_xxx", "Reply", root_id="ot_xxx")
    """

    def __init__(self, client: "Client"):
        """
        初始化发送器
        
        Args:
            client: 飞书 API Client（lark_oapi.Client）
        """
        self._client = client

    async def send(self, routing_key: str, content: str, root_id: str = "") -> None:
        """
        发送消息
        
        根据 routing_key 自动选择发送方式：
        - 单聊/群聊：使用 CreateMessage API
        - 话题（有 root_id）：使用 ReplyMessage API
        
        Args:
            routing_key: 路由键，格式为 "p2p:ou_xxx" / "group:oc_xxx" / "thread:oc_xxx:ot_xxx"
            content: 消息文本内容
            root_id: 话题根消息 ID（话题模式下可选，优先使用 routing_key 中的 thread_id）
        """
        routing = parse_routing_key(routing_key)
        if routing.type == RoutingType.THREAD and (root_id or routing.thread_id):
            await self._reply_in_thread(root_id or routing.thread_id, content)
        else:
            await self._create_message(routing, content)

    async def send_text(self, routing_key: str, content: str, root_id: str = "") -> None:
        """
        发送纯文本消息
        
        与 send() 相同，保留此方法以兼容旧接口。
        
        Args:
            routing_key: 路由键
            content: 消息文本内容
            root_id: 话题根消息 ID
        """
        await self.send(routing_key, content, root_id)

    async def _create_message(self, routing, content: str) -> None:
        """
        使用 CreateMessage API 发送消息
        
        用于单聊和群聊场景。
        
        Args:
            routing: 解析后的路由信息
            content: 消息文本内容
        """
        from lark_oapi.api.im.v1 import (
            CreateMessageRequestBody,
            CreateMessageRequest,
        )

        # 确定接收者 ID 和类型
        if routing.type == RoutingType.P2P:
            receive_id = routing.open_id
            receive_id_type = "open_id"
        else:
            receive_id = routing.chat_id
            receive_id_type = "chat_id"

        # 构建请求体
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type("text")
            .content(f'{{"text":"{content}"}}')
            .uuid(str(uuid.uuid4()))
            .build()
        )

        # 构建请求
        request = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(body)
            .build()
        )

        # 发送请求
        try:
            response = self._client.im.v1.message.acreate(request)
            if not response.success():
                logger.warning("CreateMessage failed: %s", response.msg)
            else:
                logger.debug("CreateMessage sent to %s", receive_id)
        except Exception:
            logger.exception("CreateMessage error")

    async def _reply_in_thread(self, root_id: str, content: str) -> None:
        """
        使用 ReplyMessage API 回复消息
        
        用于话题场景，回复指定的根消息。
        
        Args:
            root_id: 根消息 ID
            content: 消息文本内容
        """
        from lark_oapi.api.im.v1 import (
            ReplyMessageRequestBody,
            ReplyMessageRequest,
        )

        # 构建请求体
        body = (
            ReplyMessageRequestBody.builder()
            .msg_type("text")
            .content(f'{{"text":"{content}"}}')
            .uuid(str(uuid.uuid4()))
            .build()
        )

        # 构建请求
        request = (
            ReplyMessageRequest.builder()
            .message_id(root_id)
            .request_body(body)
            .build()
        )

        # 发送请求
        try:
            response = self._client.im.v1.message.areply(request)
            if not response.success():
                logger.warning("ReplyMessage failed: %s", response.msg)
            else:
                logger.debug("ReplyMessage sent to thread %s", root_id)
        except Exception:
            logger.exception("ReplyMessage error")
