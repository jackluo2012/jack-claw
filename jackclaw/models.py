"""
JackClaw 核心数据模型
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Attachment:
    """飞书附件元信息"""
    msg_type: str  # "image" | "file"
    file_key: str
    file_name: str


@dataclass
class InboundMessage:
    """
    标准化消息对象
    
    Attributes:
        routing_key: 路由键，p2p:ou_xxx / group:oc_xxx / thread:oc_xxx:ot_xxx
        content: 消息内容
        msg_id: 飞书 message_id
        root_id: 话题根消息 ID
        sender_id: 发送者 open_id
        ts: 创建时间（毫秒）
        is_cron: 是否为定时任务触发
        attachment: 附件信息
    """
    routing_key: str
    content: str
    msg_id: str
    root_id: str
    sender_id: str
    ts: int
    is_cron: bool = False
    attachment: Attachment | None = None


class SenderProtocol(Protocol):
    """消息发送协议"""
    async def send(self, routing_key: str, content: str, root_id: str) -> None: ...
    async def send_text(self, routing_key: str, content: str, root_id: str) -> None: ...
