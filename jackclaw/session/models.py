"""
Session 数据模型
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class MessageEntry:
    """对话历史中的一条消息"""
    role: MessageRole
    content: str
    ts: int
    feishu_msg_id: str = ""

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "content": self.content,
            "ts": self.ts,
            "feishu_msg_id": self.feishu_msg_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MessageEntry":
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            ts=data["ts"],
            feishu_msg_id=data.get("feishu_msg_id", ""),
        )


@dataclass
class Session:
    """会话对象"""
    id: str
    routing_key: str
    created_at: int
    updated_at: int
    verbose: bool = False
    messages: list[MessageEntry] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def to_dict(self) -> dict:
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
        return cls(
            id=data["id"],
            routing_key=data["routing_key"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            verbose=data.get("verbose", False),
            messages=[MessageEntry.from_dict(m) for m in data.get("messages", [])],
        )
