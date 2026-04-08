"""
配置加载模块

负责从 config.yaml 加载配置，支持环境变量替换。

配置文件格式：
    feishu:
      app_id: "${FEISHU_APP_ID}"
      app_secret: "${FEISHU_APP_SECRET}"

环境变量替换：
    ${VAR} 会被替换为环境变量 VAR 的值。

使用方式：
    cfg = load_config()
    app_id = cfg["feishu"]["app_id"]
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def load_config(config_path: Path | None = None) -> dict:
    """
    加载配置文件
    
    自动查找 config.yaml，支持环境变量替换 ${VAR}。
    
    Args:
        config_path: 配置文件路径，默认自动查找
        
    Returns:
        配置字典
        
    Raises:
        FileNotFoundError: 配置文件不存在时抛出
    """
    if config_path is None:
        cwd = Path.cwd()
        # 查找配置文件的候选路径
        candidates = [
            cwd / "config.yaml",
            cwd.parent / "config.yaml",
        ]
        for p in candidates:
            if p.exists():
                config_path = p
                break

    if config_path is None or not config_path.exists():
        raise FileNotFoundError("config.yaml not found")

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return _expand_env_vars(data)


def _expand_env_vars(obj):
    """
    递归替换 ${VAR} 为环境变量值
    
    Args:
        obj: 任意对象
        
    Returns:
        替换后的对象
    """
    if isinstance(obj, str):
        # 匹配 ${VAR} 格式
        if obj.startswith("${") and obj.endswith("}"):
            var_name = obj[2:-1]
            return os.environ.get(var_name, "")
        return obj

    elif isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}

    elif isinstance(obj, list):
        return [_expand_env_vars(item) for item in obj]

    return obj


def get_feishu_credentials(cfg: dict) -> tuple[str, str]:
    """
    获取飞书凭证
    
    从配置中提取 app_id 和 app_secret。
    
    Args:
        cfg: 配置字典
        
    Returns:
        (app_id, app_secret) 元组
        
    Raises:
        RuntimeError: 凭证未配置时抛出
    """
    feishu = cfg.get("feishu", {})
    app_id = feishu.get("app_id", "")
    app_secret = feishu.get("app_secret", "")

    if not app_id or not app_secret:
        raise RuntimeError("feishu.app_id / feishu.app_secret 不能为空")

    return app_id, app_secret
