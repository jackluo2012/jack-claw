"""
主 Agent

Phase 2: 直接调用 LLM
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from jackclaw.llm.aliyun_llm import AliyunLLM

if TYPE_CHECKING:
    from jackclaw.session.models import MessageEntry

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
你是 JackClaw，一个飞书工作助手。

职责：
- 帮助用户处理日常工作任务
- 文档处理（PDF、Word、Excel）
- 信息查询和搜索
- 日程管理和提醒

请用简洁、专业的语言回复。
"""


class MainAgent:
    """主 Agent"""

    def __init__(self, llm: AliyunLLM, system_prompt: str = ""):
        self._llm = llm
        self._system_prompt = system_prompt or _SYSTEM_PROMPT

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
            system_prompt=self._system_prompt,
        )
        logger.info("[%s] Agent reply: %s", session_id[:8], reply[:50] + "...")
        return reply
