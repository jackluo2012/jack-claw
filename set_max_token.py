#!/usr/bin/env python3
"""
从配额 JSON 文件中提取最大 token 并更新配置
使用方法:
  python set_max_token.py <json_file_path>                    # 输出环境变量
  python set_max_token.py <json_file_path> --update-config    # 更新 config.yaml
  python set_max_token.py <json_file_path> --env <file>       # 写入 .env 文件
"""

import json
import sys
import os
import re
from pathlib import Path


def find_max_token(quota_data):
    """从配额数据中找到 token 最大的模型"""
    try:
        free_tier_quotas = quota_data['data']['DataV2']['data']['data']['freeTierQuotas']

        max_quota = 0
        max_model = None
        max_model_info = None

        for quota in free_tier_quotas:
            quota_total = quota.get('quotaTotal', 0)
            model = quota.get('model', 'unknown')

            # 只考虑有效状态的配额
            if quota.get('quotaStatus') == 'VALID' and quota_total > max_quota:
                max_quota = quota_total
                max_model = model
                max_model_info = quota

        return max_model, max_quota, max_model_info

    except (KeyError, TypeError) as e:
        print(f"解析 JSON 数据时出错: {e}", file=sys.stderr)
        return None, None, None


def update_config_yaml(config_file, model, max_tokens):
    """更新 config.yaml 文件中的 agent 配置"""
    if not os.path.exists(config_file):
        print(f"警告: 配置文件 {config_file} 不存在，跳过更新", file=sys.stderr)
        return False

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 更新 agent.model
        content = re.sub(
            r'(agent:\s*\n\s*model:\s*)"([^"]*)"',
            rf'\g<1>{model}"',
            content
        )

        # 更新 agent.max_input_tokens (使用配额的 80% 作为输入限制，留一些余量)
        max_input = int(max_tokens * 0.8)
        content = re.sub(
            r'(agent:\s*[^:]*:\s*\n\s*max_input_tokens:\s*)\d+',
            rf'\g<1>{max_input}',
            content
        )

        # 更新 sub_agent_model (也使用最大模型)
        content = re.sub(
            r'(agent:\s*[^:]*:\s*\n\s*sub_agent_model:\s*)"([^"]*)"',
            rf'\g<1>{model}"',
            content
        )

        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✓ 已更新配置文件: {config_file}", file=sys.stderr)
        print(f"  - 模型: {model}", file=sys.stderr)
        print(f"  - 最大输入 token: {max_input:,}", file=sys.stderr)
        return True

    except Exception as e:
        print(f"更新配置文件时出错: {e}", file=sys.stderr)
        return False


def write_env_file(env_file, model, max_tokens):
    """写入 .env 文件"""
    try:
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(f"# 自动生成: 最大 Token 模型配置\n")
            f.write(f"MAX_MODEL_TOKEN={int(max_tokens)}\n")
            f.write(f"MAX_MODEL_NAME=\"{model}\"\n")
            f.write(f"MAX_INPUT_TOKENS={int(max_tokens * 0.8)}\n")

        print(f"✓ 已写入环境变量文件: {env_file}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"写入 .env 文件时出错: {e}", file=sys.stderr)
        return False


def main():
    if len(sys.argv) < 2:
        print("使用方法:", file=sys.stderr)
        print("  python set_max_token.py <json_file_path>                    # 输出环境变量", file=sys.stderr)
        print("  python set_max_token.py <json_file_path> --update-config    # 更新 config.yaml", file=sys.stderr)
        print("  python set_max_token.py <json_file_path> --env <file>       # 写入 .env 文件", file=sys.stderr)
        sys.exit(1)

    json_file = sys.argv[1]
    update_config = '--update-config' in sys.argv
    env_file = None

    if '--env' in sys.argv:
        env_idx = sys.argv.index('--env')
        if env_idx + 1 < len(sys.argv):
            env_file = sys.argv[env_idx + 1]

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            quota_data = json.load(f)
    except FileNotFoundError:
        print(f"错误: 文件 '{json_file}' 不存在", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败 - {e}", file=sys.stderr)
        sys.exit(1)

    model, quota, model_info = find_max_token(quota_data)

    if model is None:
        print("错误: 无法从配置文件中提取配额信息", file=sys.stderr)
        sys.exit(1)

    print(f"📊 最大 Token 模型: {model}", file=sys.stderr)
    print(f"📊 最大 Token 数量: {int(quota):,}", file=sys.stderr)
    print(file=sys.stderr)

    success = True

    # 更新 config.yaml
    if update_config:
        config_file = Path(__file__).parent / 'config.yaml'
        if not update_config_yaml(str(config_file), model, quota):
            success = False

    # 写入 .env 文件
    if env_file:
        if not write_env_file(env_file, model, quota):
            success = False

    # 如果没有指定特殊操作，输出环境变量
    if not update_config and not env_file:
        export_commands = f"""export MAX_MODEL_TOKEN={int(quota)}
export MAX_MODEL_NAME="{model}"
export MAX_INPUT_TOKENS={int(quota * 0.8)}
"""
        print(export_commands)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
