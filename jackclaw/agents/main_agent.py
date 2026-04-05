"""
主 Agent - Phase 3

集成 Skill 加载器
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from jackclaw.llm.aliyun_llm import AliyunLLM
from jackclaw.tools.skill_loader import SkillLoader

if TYPE_CHECKING:
    from jackclaw.session.models import MessageEntry

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT_TEMPLATE = """\
你是 JackClaw，一个飞书工作助手。

## 可用技能

{skills_desc}

## 使用说明

- 用户发送文件时，会自动保存到沙盒路径
- 请根据用户意图选择合适的技能
"""


class MainAgent:
    """主 Agent"""

    def __init__(
        self,
        llm: AliyunLLM,
        skills_dir: Path | None = None,
        system_prompt: str = "",
    ):
        self._llm = llm
        self._skills_dir = skills_dir
        self._skill_loader: SkillLoader | None = None
        self._system_prompt = system_prompt
        if skills_dir:
            self._skill_loader = SkillLoader(skills_dir)

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        if self._system_prompt:
            return self._system_prompt
        skills_desc = "暂无" if not self._skill_loader else self._skill_loader.get_all_descriptions()
        return _SYSTEM_PROMPT_TEMPLATE.format(skills_desc=skills_desc)

    async def run(
        self,
        user_message: str,
        history: list["MessageEntry"],
        session_id: str,
        routing_key: str = "",
        root_id: str = "",
        verbose: bool = False,
    ) -> str:
        """执行 Agent"""
        logger.info("[%s] Agent running, history_len=%d", session_id[:8], len(history))
        reply = await self._llm.chat_with_history(
            user_message=user_message,
            history=history,
            system_prompt=self._build_system_prompt(),
        )
        return reply
