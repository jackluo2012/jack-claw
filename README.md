# Phase 2: Agent 集成

> JackClaw MVP 重写 - 第 3 阶段

## 📋 概述

本阶段集成 LLM，实现 Agent 调度：
- 通义千问 API 适配器
- 主 Agent 协调
- 对话历史注入
- 系统提示构建

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│                      Runner                               │
│  - 消息入队                                              │
│  - Slash 拦截                                           │
└─────────────────────┬───────────────────────────────────┘
                      │ agent_fn()
                      ▼
┌─────────────────────────────────────────────────────────┐
│                    MainAgent                             │
│  - 构建系统提示                                          │
│  - 协调 LLM 调用                                        │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                    AliyunLLM                             │
│  - 通义千问 API                                         │
│  - Chat Completion                                      │
└─────────────────────────────────────────────────────────┘
```

## 📁 新增文件

```
jack-claw/
├── jackclaw/
│   ├── llm/                     # LLM 适配层 ⭐
│   │   └── aliyun_llm.py        # 通义千问适配器
│   │
│   └── agents/                  # Agent 执行层 ⭐
│       └── main_agent.py         # 主 Agent
```

## 🔑 核心组件

### 1. AliyunLLM (通义千问适配器)

```python
"""
阿里云通义千问 LLM 适配器

职责：
- 调用通义千问 Chat API
- 支持对话历史
- 错误处理
"""

class AliyunLLM:
    def __init__(
        self,
        model: str = "qwen-plus",      # 模型名称
        api_key: str | None = None,   # API Key
        max_tokens: int = 2000,        # 最大 token
        temperature: float = 0.7,       # 温度参数
    ):
        """
        初始化 LLM
        
        模型选择：
        - qwen-turbo: 快速，便宜
        - qwen-plus: 平衡
        - qwen-max: 强大，贵
        """
        
    async def chat(self, messages: list[dict]) -> str:
        """
        调用 Chat API
        
        Args:
            messages: [{"role": "user", "content": "..."}, ...]
        
        Returns:
            assistant 回复文本
        """
        
    async def chat_with_history(
        self,
        user_message: str,
        history: list[MessageEntry],
        system_prompt: str = "",
    ) -> str:
        """
        带历史对话的 Chat
        
        Args:
            user_message: 当前用户消息
            history: 对话历史
            system_prompt: 系统提示
        
        Returns:
            assistant 回复
        """
```

### 2. MainAgent (主 Agent)

```python
"""
主 Agent

职责：
- 协调 LLM 调用
- 构建系统提示
- 管理对话流程
"""

_SYSTEM_PROMPT = """\
你是 JackClaw，一个飞书工作助手。

职责：
- 帮助用户处理日常工作任务
- 文档处理（PDF、Word、Excel）
- 信息查询和搜索
- 日程管理和提醒

请用简洁、专业的语言回复。
"""

class MainAgent:
    def __init__(self, llm: AliyunLLM, system_prompt: str = ""):
        """
        初始化 Agent
        
        Args:
            llm: LLM 实例
            system_prompt: 自定义系统提示
        """
        
    async def run(
        self,
        user_message: str,           # 用户消息
        history: list,              # 对话历史
        session_id: str,             # 会话 ID
        routing_key: str = "",       # 路由键
        root_id: str = "",          # 话题 ID
        verbose: bool = False,      # 详细模式
    ) -> str:
        """
        执行 Agent
        
        流程：
        1. 构建系统提示
        2. 调用 LLM
        3. 返回回复
        """
```

## 🔄 对话流程

```
用户消息
    │
    ▼
MainAgent.run()
    │
    ├── 构建系统提示
    │
    ├── 转换历史格式
    │   history: [MessageEntry] → [{"role": "user", "content": "..."}]
    │
    └── LLM.chat_with_history()
            │
            ▼
        通义千问 API
            │
            ▼
        返回回复
```

## 📝 对话历史格式

```python
# MessageEntry (内部格式)
class MessageEntry:
    role: MessageRole  # USER / ASSISTANT
    content: str
    ts: int
    feishu_msg_id: str

# LLM 格式
messages = [
    {"role": "system", "content": "你是 JackClaw..."},
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮助你的？"},
    {"role": "user", "content": "帮我分析 PDF"},
    {"role": "assistant", "content": "好的，请上传 PDF 文件..."},
]
```

## 🔧 配置

```yaml
# config.yaml
agent:
  model: "qwen-plus"    # 模型选择
  max_iter: 50          # 最大迭代次数

# 环境变量
QWEN_API_KEY=sk-xxx    # 通义千问 API Key
```

## 📊 设计决策

### D-01: LLM 选择

**方案**: 通义千问

```
优点：
- 中文效果好
- 价格便宜
- 国内访问快
- Function Calling 支持
```

### D-02: Agent 框架

**MVP 方案**: 直接调用 API

```
优点：
- 简单，易理解
- 无额外依赖
- 性能好

改进：
- 后续可集成 CrewAI
- 或 LangChain
```

### D-03: 系统提示

**方案**: 模板 + 可扩展

```python
_SYSTEM_PROMPT = """\
你是 JackClaw，一个飞书工作助手。

职责：
- ...

请用简洁、专业的语言回复。
"""
```

## 🚀 运行

```bash
# 设置 API Key
export QWEN_API_KEY=sk-xxx

# 启动
python -m jackclaw.main

# TestAPI 测试
curl -X POST http://127.0.0.1:9090/api/test/message \
  -d '{"routing_key": "p2p:ou_test", "content": "你好"}'
```

## ➡️ 下一步

[Phase 3: Skills 系统](../feature/phase-3-skills)
