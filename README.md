# JackClaw

飞书本地工作助手（MVP 重写版）

## 功能特性

- **飞书消息接收** - WebSocket 长连接接收私聊/群聊/thread消息
- **消息分发** - 按 routing_key（p2p/group/thread）分队列处理
- **Agent 对话** - 支持多轮对话、会话持久化、verbose 模式
- **Skills 系统** - 动态加载外部技能（pdf/xlsx/docx 等）
- **沙盒执行** - 本地安全执行 Python/Bash 脚本
- **定时任务** - 支持 at/every/cron 三种调度模式
- **可观测性** - Prometheus metrics 暴露（端口 9091）

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/jackluo2012/jack-claw.git
cd jack-claw

# 2. 创建虚拟环境（Python 3.12+）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -e .

# 4. 配置
cp config.yaml.template config.yaml
# 编辑 config.yaml，填入飞书 App ID/Secret

# 5. 运行
jackclaw
# 或 python -m jackclaw.main
watchfiles "python -m jackclaw.main" .
```

## 配置项

### config.yaml

```yaml
feishu:
  app_id: "cli_xxxxx"
  app_secret: "xxxxx"

agent:
  model: "qwen3-max-preview"        # 主 Agent 模型
  sub_agent_model: "qwen3-max-2025-09-23"  # 子 Agent 模型
  max_iter: 50
  max_input_tokens: 30000
  timeout_s: 300

observability:
  metrics_port: 9091

data_dir: "./data"
```

### LLM 配置

新增的 LLM 配置系统支持**模型白名单**和**多 Provider**管理。

配置文件位置: `jackclaw/llm/llm_config.yaml`

```yaml
# 默认 Provider
default:
  provider: aliyun
  text_model: qwen-max

# Provider 定义
providers:
  aliyun:
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: QWEN_API_KEY  # 从环境变量读取
    models:                     # 白名单：只允许使用这些模型
      - qwen-max
      - qwen-plus
      - qwen-turbo
      # ... 更多模型

  openrouter:
    base_url: https://openrouter.ai/api/v1
    api_key_env: OPENROUTER_API_KEY
    models:
      - openai/gpt-4o
      - anthropic/claude-sonnet-4-20250514
      # ... 更多模型

# 角色模型映射（可选）
models:
  assistant:
    model: qwen3-max-preview
    temperature: 0.7
  sub_agent:
    model: qwen3-max-2025-09-23
    temperature: 0.7
  lightweight:
    model: qwen3-turbo
    temperature: 0.3
```

**使用方式:**

```python
from jackclaw.llm import LLMFactory, llm_config

# 创建默认 LLM
llm = LLMFactory.create()

# 为特定角色创建 LLM
assistant_llm = LLMFactory.create_for_role("assistant")
sub_agent_llm = LLMFactory.create_for_role("sub_agent")

# 验证模型是否在白名单中
llm_config.validate_model("qwen-max")  # 通过则无异常，不通过则抛出 ValueError

# 列出允许的模型
models = LLMFactory.list_allowed_models()
```

**核心功能:**
- ✅ **模型白名单** - 只允许使用配置中列出的模型，防止误用未授权的昂贵模型
- ✅ **多 Provider** - 支持同时配置多个 LLM Provider（阿里云、OpenRouter 等）
- ✅ **角色映射** - 不同角色（助手/子 Agent/轻量级任务）使用不同模型
- ✅ **配置验证** - 创建 LLM 时自动验证模型是否在白名单中

## 测试

```bash
pytest tests/ -v
```

## 项目结构

```
jackclaw/
├── main.py           # 入口
├── runner.py         # 消息分发器
├── models.py         # 数据模型
├── config.py         # 配置加载
├── feishu/
│   ├── listener.py   # WebSocket 监听
│   └── sender.py     # 消息发送
├── session/          # 会话管理
├── llm/              # LLM 适配器
├── agents/           # Agent 实现
├── tools/            # Skills 加载
└── sandbox/          # 沙盒执行
```

## 文档

- `docs/phase-0.md` - Phase 0: 项目骨架
- `docs/phase-1.md` - Phase 1: 核心消息处理
- `docs/phase-2.md` - Phase 2: Agent 集成
- `docs/phase-3.md` - Phase 3: Skills 系统
- `docs/phase-4.md` - Phase 4: 沙盒集成
- `docs/phase-5.md` - Phase 5: 定时任务
- `docs/phase-6.md` - Phase 6: 可观测性