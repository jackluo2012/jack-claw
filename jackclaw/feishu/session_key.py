"""
routing_key 解析

格式：
- p2p:ou_xxx           单聊
- group:oc_xxx         群聊
- thread:oc_xxx:ot_xxx 话题群
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RoutingType(str, Enum):
    P2P = "p2p"
    GROUP = "group"
    THREAD = "thread"


@dataclass
class RoutingKey:
    type: RoutingType
    open_id: str = ""
    chat_id: str = ""
    thread_id: str = ""

    @property
    def root_id(self) -> str:
        return self.thread_id


def parse_routing_key(key: str) -> RoutingKey:
    """解析 routing_key"""
    parts = key.split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid routing_key: {key}")
    routing_type = parts[0]
    if routing_type == "p2p":
        return RoutingKey(type=RoutingType.P2P, open_id=parts[1])
    elif routing_type == "group":
        return RoutingKey(type=RoutingType.GROUP, chat_id=parts[1])
    elif routing_type == "thread":
        if len(parts) < 3:
            raise ValueError(f"Invalid thread routing_key: {key}")
        return RoutingKey(type=RoutingType.THREAD, chat_id=parts[1], thread_id=parts[2])
    else:
        raise ValueError(f"Unknown routing type: {routing_type}")


def build_routing_key(
    routing_type: RoutingType,
    open_id: str = "",
    chat_id: str = "",
    thread_id: str = "",
) -> str:
    """构建 routing_key"""
    if routing_type == RoutingType.P2P:
        return f"p2p:{open_id}"
    elif routing_type == RoutingType.GROUP:
        return f"group:{chat_id}"
    elif routing_type == RoutingType.THREAD:
        return f"thread:{chat_id}:{thread_id}"
    else:
        raise ValueError(f"Unknown routing type: {routing_type}")


def resolve_routing_key(
    chat_type: str,
    sender_id: str,
    chat_id: str,
    thread_id: str | None,
) -> str:
    """将飞书事件字段映射为 routing_key 字符串
    
    Args:
        chat_type: 聊天类型 (p2p/group)
        sender_id: 发送者 open_id
        chat_id: 聊天 ID
        thread_id: 话题 ID（可选）
    
    Returns:
        routing_key 字符串
    """
    if chat_type == "p2p":
        return f"p2p:{sender_id}"
    if thread_id:
        return f"thread:{chat_id}:{thread_id}"
    return f"group:{chat_id}"
