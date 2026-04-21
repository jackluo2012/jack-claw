"""
阿里云通义千问 LLM 适配器

支持通过 LLMConfig 进行模型白名单验证和多 Provider 管理。
"""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

from crewai.llm import BaseLLM
from crewai.utilities.types import LLMMessage

from .llm_config import llm_config

logger = logging.getLogger(__name__)


class AliyunLLM(BaseLLM):
    """通义千问 LLM 适配器"""

    llm_type: str = "aliyun"
    provider: str = "aliyun"

    def __init__(
        self,
        model: str = "qwen-plus",
        api_key: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        validate_model: bool = True,  # 是否验证模型白名单
    ):
        # 验证模型是否在白名单中
        if validate_model:
            llm_config.validate_model(model)

        # 从配置获取 API key（如果未显式提供）
        if api_key is None:
            # 尝试从配置中获取 aliyun provider 的 API key
            api_key = llm_config.get_provider_api_key("aliyun")
            if not api_key:
                # 回退到环境变量
                api_key = os.environ.get("QWEN_API_KEY", "")

        # Initialize BaseLLM with required fields
        super().__init__(
            model=model,
            temperature=temperature,
            api_key=api_key,
        )
        self._max_tokens = max_tokens
        if not self.api_key:
            raise ValueError(
                "API Key 未设置。请设置 QWEN_API_KEY 环境变量，"
                "或者在 llm_config.yaml 中配置 api_key_env"
            )

    def call(
        self,
        messages: str | list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Any | None = None,
        from_agent: Any | None = None,
        response_model: type[Any] | None = None,
    ) -> str | Any:
        """同步调用 Chat API (CrewAI 接口)"""
        import asyncio
        return asyncio.run(self.acall(
            messages=messages,
            tools=tools,
            callbacks=callbacks,
            available_functions=available_functions,
            from_task=from_task,
            from_agent=from_agent,
            response_model=response_model,
        ))

    async def acall(
        self,
        messages: str | list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Any | None = None,
        from_agent: Any | None = None,
        response_model: type[Any] | None = None,
    ) -> str | Any:
        """异步调用 Chat API (CrewAI 接口)"""
        # Convert messages to standard format
        formatted_messages = self._format_messages(messages)

        # Build API request
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": {"messages": formatted_messages},
            "parameters": {
                "max_tokens": self._max_tokens,
                "temperature": self.temperature,
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
                    content = data["output"]["choices"][0]["message"]["content"]
                    return self._apply_stop_words(content)
        except Exception:
            logger.exception("LLM call failed")
            return "LLM 调用异常"
