"""
阿里云通义千问 LLM 适配器

封装通义千问 API 调用，提供统一的对话接口。

API 文档：
https://help.aliyun.com/zh/dashscope/developer-reference/api-details

支持模型：
- qwen-plus: 通义千问增强版
- qwen-turbo: 通义千问快速版
- qwen-max: 通义千问旗舰版
- qwen3-32b: 通义千问 3 32B 版本

使用方式：
    llm = AliyunLLM(model="qwen-plus", api_key="sk-xxx")
    reply = await llm.chat([{"role": "user", "content": "Hello"}])
"""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class AliyunLLM:
    """
    通义千问 LLM 适配器
    
    封装阿里云 DashScope API，支持带历史对话的多轮对话。
    """

    def __init__(
        self,
        model: str = "qwen-plus",
        api_key: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ):
        """
        初始化 LLM 适配器
        
        Args:
            model: 模型名称
            api_key: API Key，如果不提供则从环境变量 QWEN_API_KEY 读取
            max_tokens: 最大生成 token 数
            temperature: 生成温度（0-1）
        """
        self._model = model
        self._api_key = api_key or os.environ.get("QWEN_API_KEY", "")
        self._max_tokens = max_tokens
        self._temperature = temperature

        if not self._api_key:
            raise ValueError("QWEN_API_KEY not set")

    async def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        """
        调用 Chat API
        
        发送消息列表到通义千问 API，获取回复。
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            **kwargs: 额外参数，覆盖默认值
            
        Returns:
            助手回复文本
        """
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
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.warning("LLM API error: %s - %s", resp.status, text)
                        return "LLM 调用失败，请稍后重试。"

                    data = await resp.json()
                    return data["output"]["choices"][0]["message"]["content"]

        except aiohttp.ClientError:
            logger.exception("LLM API request failed")
            return "LLM 调用失败，请检查网络。"
        except Exception:
            logger.exception("LLM call failed")
            return "LLM 调用异常。"

    async def chat_with_history(
        self,
        user_message: str,
        history: list[Any],
        system_prompt: str = "",
    ) -> str:
        """
        带历史对话的 Chat
        
        自动构建包含系统提示和历史对话的消息列表。
        
        Args:
            user_message: 用户消息
            history: 对话历史（MessageEntry 列表）
            system_prompt: 系统提示
            
        Returns:
            助手回复文本
        """
        messages = []

        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加历史对话
        for entry in history:
            messages.append({
                "role": entry.role.value,
                "content": entry.content,
            })

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        return await self.chat(messages)
