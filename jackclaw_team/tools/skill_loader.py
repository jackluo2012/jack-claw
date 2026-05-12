"""
skill_loader.py — 29 课 role-scoped SkillLoaderTool

设计（v2，彻底修复并发竞争）：
- 直接把 `skills_dir` / `sandbox_skills_mount` 作为**实例级**参数传给基类 __init__
- 不再热替换基类模块全局（原实现在 4 role 并发时 race，导致 Bootstrap 串台）
"""
from __future__ import annotations

import logging
from pathlib import Path

from pydantic import PrivateAttr

from jackclaw_team.tools._skill_loader_base import SkillLoaderTool as _BaseSkillLoaderTool

logger = logging.getLogger(__name__)


class RoleScopedSkillLoaderTool(_BaseSkillLoaderTool):
    """SkillLoaderTool 的 role-scoped 子类。"""

    _role: str = PrivateAttr(default="")

    def __init__(
        self,
        *,
        role: str,
        skills_dir: Path,
        sandbox_skills_mount: str,
        session_id: str = "",
        sandbox_url: str = "",
        routing_key: str = "",
        history_all: list | None = None,
    ) -> None:
        self._role = role
        super().__init__(
            session_id=session_id,
            sandbox_url=sandbox_url,
            routing_key=routing_key,
            history_all=history_all,
            skills_dir=skills_dir,
            sandbox_mount=sandbox_skills_mount,
        )


__all__ = ["RoleScopedSkillLoaderTool"]