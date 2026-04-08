"""
JackClaw 核心数据模型

定义系统中使用的数据结构：
- Attachment: 飞书附件元信息
- InboundMessage: 标准化的入站消息
- SenderProtocol: 消息发送器协议

这些模型是消息处理流水线的基础数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Attachment:
    """
    飞书附件元信息
    
    当用户发送图片或文件时，飞书会将文件元信息包含在消息中。
    
    Attributes:
        msg_type: 消息类型，"image" 或 "file"
        file_key: 飞书文件 key，用于下载文件
        file_name: 文件名
    """
    msg_type: str  # "image" | "file"
    file_key: str
    file_name: str


@dataclass
class InboundMessage:
    """
    标准化入站消息
    
    将飞书的原始消息事件转换为统一格式，便于后续处理。
    
    Attributes:
        routing_key: 路由键，用于确定消息来源和回复目标
            - 单聊: "p2p:ou_xxx" (ou_xxx 是用户的 open_id)
            - 群聊: "group:oc_xxx" (oc_xxx 是群的 chat_id)
            - 话题: "thread:oc_xxx:ot_xxx" (ot_xxx 是根消息 ID)
        content: 消息文本内容
        msg_id: 飞书消息 ID
        root_id: 话题根消息 ID（话题模式下使用）
        sender_id: 发送者的 open_id
        ts: 消息创建时间（毫秒时间戳）
        is_cron: 是否为定时任务触发（默认 False）
        attachment: 附件信息（如果有）
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
    """
    消息发送器协议
    
    定义消息发送器必须实现的接口，用于依赖注入。
    
    实现此协议的类：
    - FeishuSender: 飞书消息发送器
    """
    async def send(self, routing_key: str, content: str, root_id: str) -> None:
        """
        发送消息
        
        Args:
            routing_key: 路由键
            content: 消息内容
            root_id: 话题根消息 ID
        """
        ...

    async def send_text(self, routing_key: str, content: str, root_id: str) -> None:
        """
        发送纯文本消息
        
        Args:
            routing_key: 路由键
            content: 消息内容
            root_id: 话题根消息 ID
        """
        ...
