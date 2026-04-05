"""
Session 管理器

职责：
- routing_key → session_id 映射
- session 数据持久化
- 对话历史管理
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
    """Session 管理器"""

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._sessions_dir = data_dir / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._sessions_dir / "index.json"
        self._index: dict[str, Any] = self._load_index()

    def _load_index(self) -> dict:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Failed to load index.json")
        return {"routing": {}, "sessions": {}}

    def _save_index(self) -> None:
        self._index_path.write_text(
            json.dumps(self._index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _now_ms(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    def _new_session_id(self) -> str:
        return f"s-{uuid.uuid4().hex[:12]}"

    async def get_or_create(self, routing_key: str) -> Session:
        """获取或创建 session"""
        routing_map = self._index.get("routing", {})
        session_id = routing_map.get(routing_key)
        if session_id:
            session = await self._load_session(session_id)
            if session:
                return session
        return await self.create_new_session(routing_key)

    async def create_new_session(self, routing_key: str) -> Session:
        """创建新 session"""
        now = self._now_ms()
        session_id = self._new_session_id()
        session = Session(
            id=session_id,
            routing_key=routing_key,
            created_at=now,
            updated_at=now,
        )
        self._index["routing"][routing_key] = session_id
        self._index["sessions"][session_id] = {
            "routing_key": routing_key,
            "created_at": now,
        }
        self._save_index()
        await self._save_session(session)
        logger.info("Created session: %s", session_id)
        return session

    async def load_history(self, session_id: str, limit: int = 20) -> list[MessageEntry]:
        """加载对话历史"""
        session = await self._load_session(session_id)
        if not session:
            return []
        messages = session.messages
        if len(messages) > limit * 2:
            messages = messages[-(limit * 2):]
        return messages

    async def append(self, session_id: str, user: str, assistant: str, feishu_msg_id: str = "") -> None:
        """追加一轮对话"""
        session = await self._load_session(session_id)
        if not session:
            return
        now = self._now_ms()
        session.messages.append(MessageEntry(
            role=MessageRole.USER,
            content=user,
            ts=now,
            feishu_msg_id=feishu_msg_id,
        ))
        session.messages.append(MessageEntry(
            role=MessageRole.ASSISTANT,
            content=assistant,
            ts=now + 1,
        ))
        session.updated_at = now
        await self._save_session(session)

    async def update_verbose(self, routing_key: str, verbose: bool) -> None:
        """更新 verbose 状态"""
        session = await self.get_or_create(routing_key)
        session.verbose = verbose
        await self._save_session(session)

    async def _load_session(self, session_id: str) -> Session | None:
        path = self._sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Session.from_dict(data)
        except Exception:
            return None

    async def _save_session(self, session: Session) -> None:
        path = self._sessions_dir / f"{session.id}.json"
        path.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
