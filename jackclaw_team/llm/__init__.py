"""
LLM 模块

提供统一的 LLM 配置管理和多 Provider 支持。

使用方式：
```python
from jackclaw.llm import LLMFactory, llm_config

# 创建默认 LLM
llm = LLMFactory.create()

# 为特定角色创建 LLM
assistant_llm = LLMFactory.create_for_role("assistant")
sub_agent_llm = LLMFactory.create_for_role("sub_agent")

# 检查模型是否允许
llm_config.validate_model("qwen-max")

# 获取允许的模型列表
models = LLMFactory.list_allowed_models()
```
"""
from .aliyun_llm import AliyunLLM
from .factory import LLMFactory
from .llm_config import LLMConfig, llm_config

__all__ = [
    "AliyunLLM",
    "LLMFactory",
    "LLMConfig",
    "llm_config",
]
