"""
LLM 配置使用示例

演示如何使用新的 LLM 配置系统
"""
from jackclaw.llm import LLMFactory, llm_config


def example_basic_usage():
    """基本使用示例"""
    # 创建默认 LLM
    llm = LLMFactory.create()
    print(f"默认 LLM: {llm.model}, 温度: {llm.temperature}")

    # 创建指定模型的 LLM
    llm = LLMFactory.create(model="qwen-turbo", temperature=0.3)
    print(f"指定模型 LLM: {llm.model}, 温度: {llm.temperature}")


def example_role_based():
    """基于角色的 LLM 创建"""
    # 为助手角色创建 LLM
    assistant_llm = LLMFactory.create_for_role("assistant")
    print(f"助手 LLM: {assistant_llm.model}")

    # 为轻量级任务创建 LLM
    lightweight_llm = LLMFactory.create_for_role("lightweight")
    print(f"轻量级 LLM: {lightweight_llm.model}")

    # 为子 Agent 创建 LLM
    sub_agent_llm = LLMFactory.create_for_role("sub_agent")
    print(f"子 Agent LLM: {sub_agent_llm.model}")


def example_validation():
    """模型白名单验证"""
    # 检查模型是否允许
    try:
        llm_config.validate_model("qwen-max")
        print("qwen-max 允许使用")
    except ValueError as e:
        print(f"错误: {e}")

    # 尝试使用未配置的模型
    try:
        llm_config.validate_model("unknown-model")
        print("unknown-model 允许使用")
    except ValueError as e:
        print(f"预期错误: {e}")


def example_list_models():
    """列出允许的模型"""
    # 列出所有允许的模型
    all_models = LLMFactory.list_allowed_models()
    print(f"所有允许的模型 ({len(all_models)} 个):")
    for model in all_models[:10]:  # 只显示前 10 个
        print(f"  - {model}")
    if len(all_models) > 10:
        print(f"  ... 还有 {len(all_models) - 10} 个模型")

    # 列出特定 Provider 的模型
    aliyun_models = LLMFactory.list_allowed_models(provider="aliyun")
    print(f"\nAliyun 允许的模型 ({len(aliyun_models)} 个):")
    for model in aliyun_models[:5]:
        print(f"  - {model}")


def example_config_access():
    """直接访问配置"""
    print(f"默认 Provider: {llm_config.default_provider}")
    print(f"默认文本模型: {llm_config.get_default_model()}")
    print(f"默认温度: {llm_config.default_temperature}")

    # 解析模型所属 Provider
    provider, model_name = llm_config.resolve_model_provider("qwen-max")
    print(f"qwen-max 属于 Provider: {provider}")

    provider, model_name = llm_config.resolve_model_provider("openai/gpt-4o")
    print(f"openai/gpt-4o 属于 Provider: {provider}")


if __name__ == "__main__":
    print("=" * 60)
    print("LLM 配置使用示例")
    print("=" * 60)

    print("\n1. 基本使用:")
    print("-" * 60)
    example_basic_usage()

    print("\n2. 基于角色的 LLM 创建:")
    print("-" * 60)
    example_role_based()

    print("\n3. 模型白名单验证:")
    print("-" * 60)
    example_validation()

    print("\n4. 列出允许的模型:")
    print("-" * 60)
    example_list_models()

    print("\n5. 直接访问配置:")
    print("-" * 60)
    example_config_access()
