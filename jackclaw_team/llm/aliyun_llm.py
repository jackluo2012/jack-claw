"""
阿里云通义千问 LLM 适配器

支持通过 LLMConfig 进行模型白名单验证和多 Provider 管理。
"""

from __future__ import annotations

import asyncio
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
        # 注意：QWEN_API_KEY 已通过 config.py 在启动时加载到环境变量
        if api_key is None:
            # 尝试从配置中获取 aliyun provider 的 API key
            api_key = llm_config.get_provider_api_key("aliyun")
            if not api_key:
                # 回退到环境变量（已由 config.py 统一加载）
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
        """同步调用 Chat API (CrewAI 接口)

        💡【异步兼容】智能检测运行环境：
        - 无事件循环：使用 asyncio.run() 创建新循环
        - 有事件循环（如在 @before_llm_call hook 中）：在新线程中创建新循环运行
        """
        import asyncio
        import threading

        async def _acall_wrapper():
            return await self.acall(
                messages=messages,
                tools=tools,
                callbacks=callbacks,
                available_functions=available_functions,
                from_task=from_task,
                from_agent=from_agent,
                response_model=response_model,
            )

        try:
            # 尝试获取当前运行中的事件循环
            asyncio.get_running_loop()

            # 💡 如果已经在异步上下文中，需要在新线程中运行以避免事件循环冲突
            result = [None]
            exception = [None]

            def run_in_thread():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result[0] = new_loop.run_until_complete(_acall_wrapper())
                    finally:
                        new_loop.close()
                except Exception as e:
                    exception[0] = e

            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()
            thread.join(timeout=30)  # 30秒超时

            if exception[0]:
                raise exception[0]
            if result[0] is None:
                raise RuntimeError("LLM call timeout or failed to complete")

            return result[0]

        except RuntimeError:
            # 没有运行中的事件循环，可以安全地使用 asyncio.run()
            return asyncio.run(_acall_wrapper())

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
            # 配置更合理的超时时间
            # connect: 连接超时, sock: 读取超时, total: 总超时
            timeout_config = aiohttp.ClientTimeout(
                total=300,      # 总超时 5 分钟
                connect=30,     # 连接超时 30 秒
                sock_read=270   # 读取超时 4.5 分钟
            )

            async with aiohttp.ClientSession() as session:
                logger.info(f"正在调用 LLM API: model={self.model}, max_tokens={self._max_tokens}")

                async with session.post(
                    url, headers=headers, json=payload, timeout=timeout_config
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"LLM API 返回错误: status={resp.status}, response={text}")
                        return f"LLM 调用失败 (HTTP {resp.status})"

                    data = await resp.json()
                    content = data["output"]["choices"][0]["message"]["content"]
                    logger.info(f"LLM API 调用成功: model={self.model}, response_length={len(content)}")
                    return self._apply_stop_words(content)

        except asyncio.TimeoutError:
            logger.error(f"LLM API 调用超时: model={self.model}, timeout=300s")
            return "LLM 调用超时，请检查网络连接或稍后重试"
        except aiohttp.ClientError as e:
            logger.error(f"LLM API 网络错误: model={self.model}, error={str(e)}")
            return f"LLM 网络错误: {str(e)}"
        except KeyError as e:
            logger.error(f"LLM API 响应格式错误: model={self.model}, missing_key={e}")
            return "LLM 响应格式错误"
        except Exception as e:
            logger.exception(f"LLM call failed: model={self.model}, error={str(e)}")
            return f"LLM 调用异常: {str(e)}"
