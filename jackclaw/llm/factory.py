"""
LLM 工厂类

支持根据配置创建不同 Provider 的 LLM 实例。
"""
from __future__ import annotations

import logging
from typing import Any

from crewai.llm import BaseLLM

from .aliyun_llm import AliyunLLM
from .llm_config import llm_config

logger = logging.getLogger(__name__)


class LLMFactory:
    """LLM 工厂类，根据配置创建 LLM 实例"""

    # 支持的 Provider 类型映射
    _providers = {
        "aliyun": AliyunLLM,
    }

    @classmethod
    def register_provider(cls, name: str, provider_class: type[BaseLLM]) -> None:
        """注册新的 Provider"""
        cls._providers[name] = provider_class

    @classmethod
    def create(
        cls,
        model: str | None = None,
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> BaseLLM:
        """
        创建 LLM 实例

        Args:
            model: 模型名称，不传则使用默认模型
            provider: Provider 名称，不传则自动解析或使用默认
            temperature: 温度参数，不传则使用配置默认值
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            LLM 实例

        Raises:
            ValueError: Provider 不支持或模型不在白名单中
        """
        # 解析模型和 provider
        if model is None:
            model = llm_config.get_default_model()

        # 解析 provider
        if provider is None:
            provider, _ = llm_config.resolve_model_provider(model)

        # 检查 provider 是否支持
        if provider not in cls._providers:
            raise ValueError(
                f"Provider '{provider}' 暂不支持。"
                f"支持的 Provider: {', '.join(cls._providers.keys())}"
            )

        # 获取温度参数
        if temperature is None:
            temperature = llm_config.default_temperature

        # 创建 LLM 实例
        provider_class = cls._providers[provider]
        return provider_class(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    @classmethod
    def create_for_role(cls, role: str, **kwargs: Any) -> BaseLLM:
        """
        为特定角色创建 LLM 实例

        Args:
            role: 角色名称（如 assistant, lightweight, vision, coder, sub_agent 等）
            **kwargs: 其他参数

        Returns:
            LLM 实例
        """
        config = llm_config.get_model_config(role)
        model = config.get("model", llm_config.get_default_model())
        temperature = config.get("temperature", llm_config.default_temperature)

        return cls.create(model=model, temperature=temperature, **kwargs)

    @classmethod
    def list_allowed_models(cls, provider: str | None = None) -> list[str]:
        """
        列出允许使用的模型列表

        Args:
            provider: Provider 名称，不传则返回所有模型的并集

        Returns:
            模型列表
        """
        if provider is None:
            return llm_config.allowed_models
        return llm_config.get_provider_models(provider)

    @classmethod
    def list_providers(cls) -> list[str]:
        """返回所有支持的 Provider"""
        return list(cls._providers.keys())

    @classmethod
    def validate_model(cls, model: str) -> bool:
        """
        验证模型是否允许使用

        Args:
            model: 模型名称

        Returns:
            是否允许

        Raises:
            ValueError: 模型不在白名单中
        """
        llm_config.validate_model(model)
        return True


__all__ = ["LLMFactory"]
