"""
主 Agent - Phase 3

集成 Skill 加载器，支持动态加载技能定义。

Agent 的职责：
- 构建系统提示（包含技能描述）
- 调用 LLM 生成回复

架构：

    Runner --> MainAgent.run() --> AliyunLLM.chat_with_history()
                                      |
                                      v
                                系统提示 + 用户消息 + 历史
                                      |
                                      v
                                   LLM 回复
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

# 系统提示模板
_SYSTEM_PROMPT_TEMPLATE = """\
你是 JackClaw，一个飞书工作助手。

## 可用技能

{skills_desc}

## 使用说明

- 用户发送文件时，会自动保存到沙盒路径
- 请根据用户意图选择合适的技能
"""


class MainAgent:
    """
    主 Agent
    
    管理 LLM 调用和技能加载。
    
    使用方式：
        llm = AliyunLLM(model="qwen-plus", api_key="sk-xxx")
        agent = MainAgent(llm=llm, skills_dir=Path("./skills"))
        reply = await agent.run("Hello", history=[], session_id="s-xxx")
    """

    def __init__(
        self,
        llm: AliyunLLM,
        skills_dir: Path | None = None,
        system_prompt: str = "",
    ):
        """
        初始化 Agent
        
        Args:
            llm: LLM 适配器
            skills_dir: Skills 目录路径
            system_prompt: 自定义系统提示（覆盖默认模板）
        """
        self._llm = llm
        self._skills_dir = skills_dir
        self._skill_loader: SkillLoader | None = None
        self._system_prompt = system_prompt

        if skills_dir and skills_dir.exists():
            self._skill_loader = SkillLoader(skills_dir)
            logger.info("SkillLoader initialized with %d skills", len(self._skill_loader.list_skills()))

    def _build_system_prompt(self) -> str:
        """
        构建系统提示
        
        如果有自定义系统提示则使用，否则使用模板。
        
        Returns:
            系统提示文本
        """
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
        """
        执行 Agent
        
        调用 LLM 生成回复。
        
        Args:
            user_message: 用户消息
            history: 对话历史
            session_id: 会话 ID
            routing_key: 路由键（预留，可用于上下文感知）
            root_id: 话题根消息 ID（预留）
            verbose: 是否详细模式（预留）
            
        Returns:
            助手回复文本
        """
        logger.info("[%s] Agent running, history_len=%d", session_id[:8], len(history))

        reply = await self._llm.chat_with_history(
            user_message=user_message,
            history=history,
            system_prompt=self._build_system_prompt(),
        )

        logger.debug("[%s] Agent reply: %s", session_id[:8], reply[:100] if reply else "")
        return reply
