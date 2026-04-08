"""
routing_key 解析与构建

routing_key 是 JackClaw 中用于标识消息来源和路由的核心概念。

格式：
- 单聊: "p2p:ou_xxx"           (ou_xxx 是用户的 open_id)
- 群聊: "group:oc_xxx"         (oc_xxx 是群的 chat_id)
- 话题: "thread:oc_xxx:ot_xxx" (ot_xxx 是根消息 ID)

使用方式：
    # 解析
    routing = parse_routing_key("p2p:ou_abc123")
    print(routing.type)  # RoutingType.P2P
    print(routing.open_id)  # "ou_abc123"
    
    # 构建
    key = build_routing_key(RoutingType.P2P, open_id="ou_abc123")
    print(key)  # "p2p:ou_abc123"
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RoutingType(str, Enum):
    """
    路由类型
    
    标识消息的来源类型。
    """
    P2P = "p2p"        # 单聊
    GROUP = "group"    # 群聊
    THREAD = "thread"  # 话题


@dataclass
class RoutingKey:
    """
    解析后的路由信息
    
    包含路由类型和相关 ID。
    
    Attributes:
        type: 路由类型
        open_id: 用户 open_id（单聊时使用）
        chat_id: 群 chat_id（群聊和话题时使用）
        thread_id: 根消息 ID（话题时使用）
    """
    type: RoutingType
    open_id: str = ""
    chat_id: str = ""
    thread_id: str = ""

    @property
    def root_id(self) -> str:
        """话题根消息 ID（thread_id 的别名）"""
        return self.thread_id


def parse_routing_key(key: str) -> RoutingKey:
    """
    解析 routing_key
    
    将字符串格式的 routing_key 解析为 RoutingKey 对象。
    
    Args:
        key: routing_key 字符串
        
    Returns:
        RoutingKey 对象
        
    Raises:
        ValueError: 格式无效时抛出
    """
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
        return RoutingKey(
            type=RoutingType.THREAD,
            chat_id=parts[1],
            thread_id=parts[2],
        )

    else:
        raise ValueError(f"Unknown routing type: {routing_type}")


def build_routing_key(
    routing_type: RoutingType,
    open_id: str = "",
    chat_id: str = "",
    thread_id: str = "",
) -> str:
    """
    构建 routing_key
    
    根据路由类型和相关 ID 构建字符串格式的 routing_key。
    
    Args:
        routing_type: 路由类型
        open_id: 用户 open_id（单聊时必填）
        chat_id: 群 chat_id（群聊和话题时必填）
        thread_id: 根消息 ID（话题时必填）
        
    Returns:
        routing_key 字符串
        
    Raises:
        ValueError: 参数不匹配时抛出
    """
    if routing_type == RoutingType.P2P:
        if not open_id:
            raise ValueError("open_id required for P2P routing")
        return f"p2p:{open_id}"

    elif routing_type == RoutingType.GROUP:
        if not chat_id:
            raise ValueError("chat_id required for GROUP routing")
        return f"group:{chat_id}"

    elif routing_type == RoutingType.THREAD:
        if not chat_id or not thread_id:
            raise ValueError("chat_id and thread_id required for THREAD routing")
        return f"thread:{chat_id}:{thread_id}"

    else:
        raise ValueError(f"Unknown routing type: {routing_type}")
