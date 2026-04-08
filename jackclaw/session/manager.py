"""
Session 管理器

负责会话的创建、加载、保存和历史管理。

核心职责：
- routing_key → session_id 映射
- session 数据持久化（JSON 文件）
- 对话历史管理

文件结构：
    data/
    └── sessions/
        ├── index.json          # routing_key → session_id 映射
        ├── s-abc123.json       # 会话文件
        └── s-xyz789.json

使用方式：
    mgr = SessionManager(data_dir=Path("./data"))
    session = await mgr.get_or_create("p2p:ou_xxx")
    history = await mgr.load_history(session.id)
    await mgr.append(session.id, user="Hi", assistant="Hello!")
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jackclaw.session.models import Session, MessageEntry, MessageRole

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Session 管理器
    
    管理会话的完整生命周期。
    
    Attributes:
        _data_dir: 数据根目录
        _sessions_dir: 会话文件目录
        _index_path: 索引文件路径
        _index: 内存中的索引数据
    """

    def __init__(self, data_dir: Path):
        """
        初始化管理器
        
        Args:
            data_dir: 数据根目录
        """
        self._data_dir = data_dir
        self._sessions_dir = data_dir / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._sessions_dir / "index.json"
        self._index: dict[str, Any] = self._load_index()

    def _load_index(self) -> dict:
        """
        加载索引文件
        
        Returns:
            索引数据字典
        """
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Failed to load index.json, starting fresh")
        return {"routing": {}, "sessions": {}}

    def _save_index(self) -> None:
        """保存索引文件"""
        self._index_path.write_text(
            json.dumps(self._index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _now_ms(self) -> int:
        """获取当前时间戳（毫秒）"""
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    def _new_session_id(self) -> str:
        """生成新的会话 ID"""
        return f"s-{uuid.uuid4().hex[:12]}"

    async def get_or_create(self, routing_key: str) -> Session:
        """
        获取或创建会话
        
        如果 routing_key 已有对应会话，则加载；否则创建新会话。
        
        Args:
            routing_key: 路由键
            
        Returns:
            Session 对象
        """
        routing_map = self._index.get("routing", {})
        session_id = routing_map.get(routing_key)

        if session_id:
            session = await self._load_session(session_id)
            if session:
                return session

        return await self.create_new_session(routing_key)

    async def create_new_session(self, routing_key: str) -> Session:
        """
        创建新会话
        
        同时更新索引和保存会话文件。
        
        Args:
            routing_key: 路由键
            
        Returns:
            新创建的 Session 对象
        """
        now = self._now_ms()
        session_id = self._new_session_id()

        session = Session(
            id=session_id,
            routing_key=routing_key,
            created_at=now,
            updated_at=now,
        )

        # 更新索引
        self._index["routing"][routing_key] = session_id
        self._index["sessions"][session_id] = {
            "routing_key": routing_key,
            "created_at": now,
        }
        self._save_index()

        # 保存会话文件
        await self._save_session(session)

        logger.info("Created session: %s for routing_key: %s", session_id, routing_key)
        return session

    async def load_history(self, session_id: str, limit: int = 20) -> list[MessageEntry]:
        """
        加载对话历史
        
        返回最近的 N 轮对话（每轮包含用户消息和助手回复）。
        
        Args:
            session_id: 会话 ID
            limit: 最大轮数（默认 20）
            
        Returns:
            消息列表
        """
        session = await self._load_session(session_id)
        if not session:
            return []

        messages = session.messages
        # 限制历史长度（每轮 2 条消息）
        if len(messages) > limit * 2:
            messages = messages[-(limit * 2):]

        return messages

    async def append(self, session_id: str, user: str, assistant: str, feishu_msg_id: str = "") -> None:
        """
        追加一轮对话
        
        同时添加用户消息和助手回复。
        
        Args:
            session_id: 会话 ID
            user: 用户消息
            assistant: 助手回复
            feishu_msg_id: 飞书消息 ID
        """
        session = await self._load_session(session_id)
        if not session:
            logger.warning("Session not found: %s", session_id)
            return

        now = self._now_ms()

        # 添加用户消息
        session.messages.append(MessageEntry(
            role=MessageRole.USER,
            content=user,
            ts=now,
            feishu_msg_id=feishu_msg_id,
        ))

        # 添加助手回复
        session.messages.append(MessageEntry(
            role=MessageRole.ASSISTANT,
            content=assistant,
            ts=now + 1,
        ))

        session.updated_at = now
        await self._save_session(session)

    async def update_verbose(self, routing_key: str, verbose: bool) -> None:
        """
        更新会话的详细模式状态
        
        Args:
            routing_key: 路由键
            verbose: 是否开启详细模式
        """
        session = await self.get_or_create(routing_key)
        session.verbose = verbose
        await self._save_session(session)

    async def _load_session(self, session_id: str) -> Session | None:
        """
        加载会话文件
        
        Args:
            session_id: 会话 ID
            
        Returns:
            Session 对象，如果不存在则返回 None
        """
        path = self._sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Session.from_dict(data)
        except Exception:
            logger.exception("Failed to load session: %s", session_id)
            return None

    async def _save_session(self, session: Session) -> None:
        """
        保存会话文件
        
        Args:
            session: Session 对象
        """
        path = self._sessions_dir / f"{session.id}.json"
        path.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
