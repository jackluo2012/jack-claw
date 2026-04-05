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
    """递归替换 ${VAR} 为环境变量值"""
    if isinstance(obj, str):
        if obj.startswith("${") and obj.endswith("}"):
            return os.environ.get(obj[2:-1], "")
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
        raise RuntimeError("feishu.app_id / feishu.app_secret 不能为空")
    return app_id, app_secret
