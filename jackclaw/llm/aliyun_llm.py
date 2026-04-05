"""
阿里云通义千问 LLM 适配器
"""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class AliyunLLM:
    """通义千问 LLM 适配器"""

    def __init__(
        self,
        model: str = "qwen-plus",
        api_key: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ):
        self._model = model
        self._api_key = api_key or os.environ.get("QWEN_API_KEY", "")
        self._max_tokens = max_tokens
        self._temperature = temperature
        if not self._api_key:
            raise ValueError("QWEN_API_KEY not set")

    async def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        """调用 Chat API"""
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "input": {"messages": messages},
            "parameters": {
                "max_tokens": kwargs.get("max_tokens", self._max_tokens),
                "temperature": kwargs.get("temperature", self._temperature),
                "result_format": "message",
            },
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.warning("LLM API error: %s - %s", resp.status, text)
                        return "LLM 调用失败"
                    data = await resp.json()
                    return data["output"]["choices"][0]["message"]["content"]
        except Exception:
            logger.exception("LLM call failed")
            return "LLM 调用异常"

    async def chat_with_history(self, user_message: str, history: list[Any], system_prompt: str = "") -> str:
        """带历史对话的 Chat"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for entry in history:
            messages.append({"role": entry.role.value, "content": entry.content})
        messages.append({"role": "user", "content": user_message})
        return await self.chat(messages)
