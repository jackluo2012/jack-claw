"""
Session 数据模型

定义会话相关的数据结构：
- MessageRole: 消息角色枚举（用户/助手）
- MessageEntry: 单条消息记录
- Session: 会话对象

会话数据持久化到 JSON 文件，每个会话一个文件。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    """
    消息角色
    
    用于标识消息是来自用户还是助手。
    """
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class MessageEntry:
    """
    对话历史中的一条消息
    
    记录消息的角色、内容、时间戳等元信息。
    
    Attributes:
        role: 消息角色（用户/助手）
        content: 消息内容
        ts: 时间戳（毫秒）
        feishu_msg_id: 飞书消息 ID（用于追踪）
    """
    role: MessageRole
    content: str
    ts: int
    feishu_msg_id: str = ""

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "role": self.role.value,
            "content": self.content,
            "ts": self.ts,
            "feishu_msg_id": self.feishu_msg_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MessageEntry":
        """从字典反序列化"""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            ts=data["ts"],
            feishu_msg_id=data.get("feishu_msg_id", ""),
        )


@dataclass
class Session:
    """
    会话对象
    
    管理一次对话的完整状态，包括消息历史、配置等。
    
    Attributes:
        id: 会话 ID，格式为 "s-{uuid[:12]}"
        routing_key: 路由键，标识会话来源
        created_at: 创建时间（毫秒时间戳）
        updated_at: 最后更新时间（毫秒时间戳）
        verbose: 是否开启详细模式
        messages: 消息历史列表
    """
    id: str
    routing_key: str
    created_at: int
    updated_at: int
    verbose: bool = False
    messages: list[MessageEntry] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        """消息数量"""
        return len(self.messages)

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "routing_key": self.routing_key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "verbose": self.verbose,
            "messages": [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """从字典反序列化"""
        return cls(
            id=data["id"],
            routing_key=data["routing_key"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            verbose=data.get("verbose", False),
            messages=[MessageEntry.from_dict(m) for m in data.get("messages", [])],
        )
