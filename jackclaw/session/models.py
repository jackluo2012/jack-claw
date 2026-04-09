"""Session 数据模型"""

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
    """JSONL 中的一条对话消息"""
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


# 以下为 index.json 格式的轻量级结构（供 SessionManager 内部使用）

@dataclass(frozen=True)
class SessionEntry:
    """index.json 中的单个 session 元数据快照"""
    id: str  # "s-{uuid}"
    created_at: str  # ISO 8601
    verbose: bool = False
    message_count: int = 0


@dataclass(frozen=True)
class RoutingEntry:
    """index.json 中一个 routing_key 的完整数据"""
    active_session_id: str
    sessions: list[SessionEntry] = field(default_factory=list)