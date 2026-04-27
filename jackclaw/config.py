"""
配置加载模块

职责：
- 从 config.yaml 加载配置
- 支持环境变量替换 ${VAR}
- 提供配置项访问接口
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ── 统一在模块加载时自动加载 .env ─────────────────────────────────────
# 优先找项目根目录的 .env，找不到则静默跳过（开发/生产环境可能直接用系统环境变量）
def _find_dotenv() -> Path | None:
    """从本文件位置向上查找 .env"""
    try:
        # jackclaw/config.py -> jackclaw/ -> 项目根目录
        base = Path(__file__).resolve().parent.parent
    except Exception:
        base = Path.cwd()
    candidates = [base / ".env", base.parent / ".env"]
    for p in candidates:
        if p.exists():
            return p
    return None

_dotenv_path = _find_dotenv()
if _dotenv_path:
    load_dotenv(_dotenv_path)


# ── 配置加载函数 ────────────────────────────────────────────────────────

def load_config(config_path: Path | None = None) -> dict:
    """
    加载配置文件，支持环境变量替换

    Args:
        config_path: 配置文件路径，默认自动查找

    Returns:
        配置字典
    """
    if config_path is None:
        cwd = Path.cwd()
        candidates = [cwd / "config.yaml", cwd.parent / "config.yaml"]
        for p in candidates:
            if p.exists():
                config_path = p
                break

    if config_path is None or not config_path.exists():
        raise FileNotFoundError("config.yaml not found")

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return _expand_env_vars(data)


def _expand_env_vars(obj):
    """递归替换 ${VAR} 和 ${VAR:-default} 为环境变量值"""
    if isinstance(obj, str):
        dollar = "${"
        if obj.startswith(dollar) and obj.endswith("}"):
            inner = obj[2:-1]
            # 支持 ${VAR:-default} 语法
            if ":-" in inner:
                var_name, _, default = inner.partition(":-")
                return os.environ.get(var_name, default)
            return os.environ.get(inner, "")
        return obj
    elif isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars(item) for item in obj]
    return obj


def get_feishu_credentials(cfg: dict) -> tuple[str, str]:
    """获取飞书凭证"""
    feishu = cfg.get("feishu", {})
    app_id = feishu.get("app_id", "")
    app_secret = feishu.get("app_secret", "")
    if not app_id or not app_secret:
        raise RuntimeError(
            "feishu.app_id / feishu.app_secret 不能为空，"
            "请检查 .env 中的 FEISHU_APP_ID / FEISHU_APP_SECRET"
        )
    return app_id, app_secret
