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

### 方式一：一键初始化（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/jackluo2012/jack-claw.git
cd jack-claw

# 2. 运行初始化脚本
./init.sh
```

初始化脚本会自动完成以下操作：
- 创建 Python 虚拟环境
- 安装所有依赖包
- 生成 config.yaml 配置文件
- 创建必要的数据目录
- 初始化工作区文件
- 询问是否启动 Docker 服务（pgvector 和 sandbox）

### 方式二：手动安装

```bash
# 1. 创建虚拟环境（Python 3.12+）
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirements.txt
# 或 pip install -e .

# 3. 配置
cp config.yaml.template config.yaml
# 编辑 config.yaml，填入飞书 App ID/Secret

# 4. 创建必要目录
mkdir -p data/workspace data/ctx data/logs data/cron
```

### 启动服务

```bash
# 方式一：使用启动脚本（推荐）
./start.sh

# 方式二：手动启动
source .venv/bin/activate
python3 -m jackclaw.main
```

### 验证运行

```bash
# 查看日志
tail -f data/logs/jackclaw.log

# 看到 "jackclaw ready" 表示启动成功
```

## 配置项

### config.yaml

完整配置示例（参考 config.yaml.example）：

```yaml
# 工作区配置
workspace:
  id: "jackclaw-default"
  name: "JackClaw 工作助手"

# 飞书配置（必填）
feishu:
  app_id: "cli_纟xx"              # 从飞书开放平台获取
  app_secret: "xxxxx"  # 从飞书开放平台获取
  encrypt_key: ""                             # 可选，事件加密
  verification_token: ""                      # 可选，验证令牌

# 机器人配置
bot:
  loading_message: "思考中..."
  prefix: ""

# Agent 配置
agent:
  model: "qwen3-max-preview"                  # 主 Agent 模型
  max_iter: 50
  max_input_tokens: 30000
  sub_agent_model: "qwen3-max-2025-09-23"     # 子 Agent 模型
  sub_agent_max_iter: 20
  timeout_s: 300

# Skills 配置
skills:
  global_dir: "../skills"                     # 全局技能目录
  local_dir: "./skills"                       # 本地技能目录

# 百度搜索配置（用于 baidu_search Skill）
baidu:
  api_key: ""                                 # 百度千帆 API Key，可从环境变量 BAIDU_API_KEY 读取

# Sandbox 配置
sandbox:
  url: "http://localhost:8022/mcp"            # Sandbox 服务地址
  workspace_dir: "/workspace"
  timeout_s: 120
  max_retries: 2

# Memory 配置
memory:
  workspace_dir: "./data/workspace"           # 工作区目录
  ctx_dir: "./data/ctx"                       # 上下文存储目录
  db_dsn: "${MEMORY_DB_DSN:-postgresql://jackclaw:jackclaw123@localhost:5432/jackclaw_memory}"  # pgvector 连接串

# Session 配置
session:
  max_history_turns: 20

# Runner 配置
runner:
  queue_idle_timeout_s: 300
  max_queue_size: 10

# Sender 配置
sender:
  max_retries: 3
  retry_backoff: [1, 2, 4]

# 数据目录
data_dir: "./data"

# 调试配置
debug:
  enable_test_api: false                      # 是否启用测试 API
  test_api_port: 9090
  test_api_host: "127.0.0.1"

# 可观测性配置
observability:
  enable_metrics: false                       # 是否启用 Prometheus metrics
  metrics_port: 9091
```

### Docker 服务

#### pgvector 数据库（可选）

用于向量搜索记忆索引：

```bash
# 启动 pgvector 服务
docker compose -f pgvector-docker-compose.yaml up -d

# 查看日志
docker compose -f pgvector-docker-compose.yaml logs -f

# 停止服务
docker compose -f pgvector-docker-compose.yaml down
```

默认连接信息：
- Host: localhost
- Port: 5432
- Database: jackclaw_memory
- User: jackclaw
- Password: jackclaw123

#### Sandbox 服务（可选）

用于安全执行 Python/Bash 脚本：

```bash
# 启动 sandbox 服务
docker compose -f sandbox-docker-compose.yaml up -d

# 查看日志
docker compose -f sandbox-docker-compose.yaml logs -f

# 停止服务
docker compose -f sandbox-docker-compose.yaml down
```

默认连接信息：
- URL: http://localhost:8022/mcp

### 环境变量

支持通过环境变量覆盖敏感配置：

```bash
# 飞书配置
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="xxx"

# pgvector 数据库
export MEMORY_DB_DSN="postgresql://user:pass@localhost:5432/dbname"

# 百度搜索（用于 baidu_search Skill）
export BAIDU_API_KEY="xxx"

# 阿里云通义千问 API
export QWEN_API_KEY="sk-xxx"
```

### 飞书应用配置

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建应用，获取 App ID 和 App Secret
3. 配置权限：
   - 获取与发送消息
   - 读取用户信息
   - 访问文件
4. 设置事件订阅（如需要）

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
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_runner.py -v
```

## 常见问题

### 1. 程序启动失败

**问题**: `TypeError: setup_logging() missing 1 required positional argument`

**解决**: 确保使用最新代码，运行 `git pull` 更新

**问题**: `FileNotFoundError: config.yaml not found`

**解决**: 运行 `cp config.yaml.template config.yaml` 生成配置文件

### 2. 飞书连接失败

**问题**: 飞书消息无法接收

**解决**:
- 检查 config.yaml 中的 app_id 和 app_secret 是否正确
- 确认飞书应用已发布并处于启用状态
- 检查网络连接

### 3. Sandbox 连接失败

**问题**: `sandbox connection error`

**解决**:
- 启动 Sandbox 服务: `docker compose -f sandbox-docker-compose.yaml up -d`
- 检查配置文件中的 sandbox.url 是否正确
- 验证端口是否被占用: `netstat -tlnp | grep 8022`

### 4. pgvector 连接失败

**问题**: `connection to server at "localhost" (127.0.0.1), port 5432 failed`

**解决**:
- 启动 pgvector 服务: `docker compose -f pgvector-docker-compose.yaml up -d`
- 检查数据库是否正常启动: `docker compose -f pgvector-docker-compose.yaml ps`
- 验证连接串配置是否正确

### 5. 技能无法加载

**问题**: Skills 相关功能不可用

**解决**:
- 检查 skills 目录是否存在且有权限
- 确认 config.yaml 中的 skills 配置路径正确
- 查看日志: `tail -f data/logs/jackclaw.log`

## 日志和调试

### 查看日志

```bash
# 实时查看日志
tail -f data/logs/jackclaw.log

# 查看最近 100 行
tail -n 100 data/logs/jackclaw.log

# 搜索错误日志
grep ERROR data/logs/jackclaw.log
```

### 调试模式

启用测试 API 进行调试：

```yaml
# config.yaml
debug:
  enable_test_api: true
  test_api_port: 9090
  test_api_host: "0.0.0.0"  # 允许外部访问
```

然后通过 HTTP API 测试：

```bash
curl -X POST http://localhost:9090/api/test \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'
```

### Prometheus Metrics

启用 Metrics 收集：

```yaml
# config.yaml
observability:
  enable_metrics: true
  metrics_port: 9091
```

访问 metrics: `http://localhost:9091/metrics`

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