#!/usr/bin/env python3
"""
密钥配置检查工具

验证 .env 文件中的密钥配置是否正确，并检查是否有潜在的安全问题。
"""

import os
import sys
from pathlib import Path


def check_env_config():
    """检查环境变量配置"""
    # 加载 .env
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        print("❌ 错误：.env 文件不存在")
        print("   请复制 .env.example 为 .env 并填入你的密钥")
        return False

    # 导入 config 来加载环境变量
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from jackclaw.config import load_config, get_feishu_credentials

        cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        return False

    all_ok = True

    # 检查飞书凭证
    print("=" * 60)
    print("检查飞书凭证")
    print("=" * 60)
    try:
        app_id, app_secret = get_feishu_credentials(cfg)
        print(f"✅ FEISHU_APP_ID: {app_id}")
        print(f"✅ FEISHU_APP_SECRET: {'*' * 10} (已隐藏)")
    except Exception as e:
        print(f"❌ 飞书凭证检查失败: {e}")
        all_ok = False

    # 检查阿里云 API Key
    print()
    print("=" * 60)
    print("检查阿里云 API Key")
    print("=" * 60)
    qwen_api_key = os.environ.get("QWEN_API_KEY", "")
    if qwen_api_key:
        print(f"✅ QWEN_API_KEY: {'*' * 10}...{qwen_api_key[-4:]} (已隐藏)")
    else:
        print("⚠️  QWEN_API_KEY 未设置（如果使用其他 LLM provider，可以忽略）")

    # 检查百度 API Key
    print()
    print("=" * 60)
    print("检查百度 API Key")
    print("=" * 60)
    baidu_api_key = cfg.get("baidu", {}).get("api_key", "")
    if baidu_api_key:
        print(f"✅ BAIDU_API_KEY: {'*' * 10}...{baidu_api_key[-4:]} (已隐藏)")
    else:
        print("⚠️  BAIDU_API_KEY 未设置（baidu_search skill 将不可用）")

    # 检查数据库连接串
    print()
    print("=" * 60)
    print("检查数据库连接串")
    print("=" * 60)
    db_dsn = cfg.get("memory", {}).get("db_dsn", "")
    if db_dsn:
        # 隐藏密码部分
        import re
        masked_dsn = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', db_dsn)
        print(f"✅ MEMORY_DB_DSN: {masked_dsn}")
    else:
        print("⚠️  MEMORY_DB_DSN 未设置（将使用内存存储）")

    # 检查文件权限
    print()
    print("=" * 60)
    print("检查文件权限")
    print("=" * 60)
    if env_path.exists():
        stat_info = env_path.stat()
        mode = oct(stat_info.st_mode)[-3:]
        if mode == "600":
            print(f"✅ .env 文件权限正确: {mode}")
        else:
            print(f"⚠️  .env 文件权限过于宽松: {mode}（建议设置为 600）")
            try:
                env_path.chmod(0o600)
                print(f"   已自动修复为 600")
            except Exception:
                print(f"   无法自动修复，请手动运行: chmod 600 {env_path}")

    # 检查 .gitignore
    print()
    print("=" * 60)
    print("检查 Git 配置")
    print("=" * 60)
    gitignore_path = Path(__file__).parent.parent / ".gitignore"
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if ".env" in content:
            print("✅ .env 已在 .gitignore 中")
        else:
            print("❌ .env 未在 .gitignore 中，请添加")
            all_ok = False

    # 总结
    print()
    print("=" * 60)
    if all_ok:
        print("✅ 所有检查通过！配置安全且正确。")
    else:
        print("⚠️  发现一些问题，请修复后再运行程序。")
    print("=" * 60)

    return all_ok


if __name__ == "__main__":
    success = check_env_config()
    sys.exit(0 if success else 1)
