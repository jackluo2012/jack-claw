# Phase 0: 项目骨架

> JackClaw MVP 重写 - 第 1 阶段

## 📋 概述

本阶段创建最小可运行的项目骨架，包含：
- 项目结构定义
- 依赖配置
- 核心数据模型
- 配置加载模块
- 进程入口

## 🏗️ 架构

```
jack-claw/
├── jackclaw/              # 主包
│   ├── __init__.py       # 包初始化
│   ├── config.py         # 配置加载
│   ├── main.py           # 进程入口
│   └── models.py         # 数据模型
├── tests/                # 测试
│   └── test_config.py
├── pyproject.toml        # 项目配置
└── README.md
```

## 📁 文件说明

### jackclaw/__init__.py
```python
"""
JackClaw — 飞书本地工作助手

架构分层：
- 接入层: feishu/
- 调度层: runner.py, session/
- 执行层: agents/, llm/
- 工具层: tools/, skills/
- 基础层: sandbox/, cron/, cleanup/, observability/
"""
__version__ = "0.1.0"
```

### jackclaw/config.py
```python
"""
配置加载模块

职责：
- 从 config.yaml 加载配置
- 支持环境变量替换 ${VAR}
- 提供配置项访问接口

使用示例：
    cfg = load_config()
    app_id, app_secret = get_feishu_credentials(cfg)
"""

def load_config(config_path: Path | None = None) -> dict:
    """加载配置文件，支持环境变量替换"""

def get_feishu_credentials(cfg: dict) -> tuple[str, str]:
    """获取飞书凭证"""
```

### jackclaw/models.py
```python
"""
核心数据模型

定义框架内流转的核心数据结构
"""

@dataclass(frozen=True)
class Attachment:
    """飞书附件元信息
    - msg_type: "image" | "file"
    - file_key: 飞书文件标识
    - file_name: 文件名
    """

@dataclass
class InboundMessage:
    """标准化消息对象
    - routing_key: 路由键
    - content: 消息内容
    - msg_id: 飞书 message_id
    - sender_id: 发送者 open_id
    - ts: 创建时间（毫秒）
    - is_cron: 是否为定时任务
    - attachment: 附件信息
    """

class SenderProtocol(Protocol):
    """消息发送协议"""
```

### jackclaw/main.py
```python
"""
进程入口 - Phase 0

仅包含最小可运行骨架
"""

def setup_logging() -> None:
    """初始化日志"""

async def async_main() -> None:
    """异步主函数"""
    # 1. 加载配置
    # 2. 获取凭证
    # 3. 打印就绪信息
```

## 🔧 依赖

```toml
dependencies = [
    "aiohttp>=3.9",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "lark-oapi>=1.0",
    "croniter>=1.0",
]
```

## 🚀 运行

```bash
pip install -e .
cp config.yaml.template config.yaml
python -m jackclaw.main
```

## 📖 设计决策

| 决策 | 说明 |
|------|------|
| YAML 配置 | 可读性好，支持注释 |
| dataclass 模型 | 标准库，无依赖 |
| asyncio.run() | Python 3.7+ 标准 |

## ➡️ 下一步

[Phase 1: 核心消息处理](./feature/phase-1-messaging)
