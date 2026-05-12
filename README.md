# JackClaw - 飞书智能工作助手

JackClaw 是一个基于飞书的智能工作助手系统，提供个人助手和团队协作两种模式。

## 📦 项目概述

JackClaw 包含两个核心模块：

### 1. JackClaw（个人助手模式）
- **飞书消息接收** - WebSocket 长连接接收私聊/群聊/thread 消息
- **AI 对话助手** - 支持多轮对话、会话持久化
- **技能系统** - 动态加载外部技能（PDF/Excel/Word/搜索等）
- **沙盒执行** - 本地安全执行 Python/Bash 脚本
- **定时任务** - 支持 at/every/cron 三种调度模式
- **可观测性** - Prometheus metrics 暴露（端口 9091）

### 2. JackClaw Team（团队协作模式）
- **多角色协作** - Manager/PM/RD/QA 四个角色协同工作
- **智能任务分配** - 基于 SOP 的任务拆解和分配
- **邮箱系统** - 角色间异步通讯机制
- **心跳机制** - 定期检查和处理待办事项
- **项目全流程** - 从需求澄清到设计开发到测试交付的完整流程

## 🚀 快速开始

### 环境要求
- Python 3.12+
- Docker（用于 pgvector 和 sandbox 服务）

### 1. 克隆项目

```bash
git clone https://github.com/jackluo2012/jack-claw.git
cd jack-claw
```

### 2. 初始化环境

```bash
./init.sh
```

这个脚本会：
- 创建 Python 虚拟环境
- 安装依赖包
- 生成配置文件
- 创建必要目录
- 询问是否启动 Docker 服务

### 3. 配置环境变量

编辑项目根目录的 `.env` 文件：

```bash
# 飞书开放平台 https://open.feishu.cn/ → 应用 → 凭证与基础信息
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret

# 阿里云百炼 https://bailian.console.aliyun.com/
QWEN_API_KEY=your_qwen_api_key

# 百度千帆（用于搜索技能）
BAIDU_API_KEY=your_baidu_api_key

# pgvector 连接串（可选，用于语义检索）
MEMORY_DB_DSN=postgresql://user:pass@localhost:5432/jackclaw
```

### 4. 启动服务

#### 启动 JackClaw（个人助手）
```bash
./start.sh
# 或
source .venv/bin/activate
python3 -m jackclaw.main
```

#### 启动 JackClaw Team（团队协作）
```bash
source .venv/bin/activate
python3 -m jackclaw_team.main
```

#### 仅 Cron 模式（不启动飞书监听）
```bash
source .venv/bin/activate
python3 -m jackclaw_team.main --no-feishu
```

## 📂 项目结构

```
jack-claw/
├── .env                    # 所有密钥配置（不入 Git）
├── config.yaml             # JackClaw 配置
├── jackclaw_team/
│   └── config.yaml         # JackClaw Team 配置
├── jackclaw/               # 个人助手模块
│   ├── main.py             # 入口文件
│   ├── config.py           # 配置加载
│   ├── feishu/             # 飞书集成
│   ├── session/            # 会话管理
│   ├── llm/                # LLM 适配器
│   ├── agents/             # Agent 实现
│   ├── skills/             # 技能系统
│   └── sandbox/            # 沙盒执行
├── jackclaw_team/          # 团队协作模块
│   ├── main.py             # 入口文件
│   ├── agents/             # 多角色 Agent
│   ├── workspace/          # 工作空间
│   │   ├── manager/        # 项目经理角色
│   │   ├── pm/             # 产品经理角色
│   │   ├── rd/             # 研发角色
│   │   ├── qa/             # 测试角色
│   │   └── shared/         # 共享项目空间
│   └── cron/               # 定时任务
├── data/                   # 数据目录
│   ├── workspace/          # 工作区
│   ├── ctx/                # 上下文
│   ├── logs/               # 日志
│   └── sessions/           # 会话记录
├── start.sh                # 启动脚本
├── stop.sh                 # 停止脚本
└── init.sh                 # 初始化脚本
```

## 🔧 配置说明

### JackClaw 配置（config.yaml）

```yaml
workspace:
  id: jackclaw-default
  name: JackClaw 个人助手

feishu:
  app_id: ${FEISHU_APP_ID}
  app_secret: ${FEISHU_APP_SECRET}

agent:
  model: qwen-turbo-1101
  max_iter: 50
  timeout_s: 300

sandbox:
  url: http://localhost:8022/mcp
  timeout_s: 120

memory:
  workspace_dir: ./data/workspace
  ctx_dir: ./data/ctx
  db_dsn: ${MEMORY_DB_DSN:-}

session:
  max_history_turns: 20
```

### JackClaw Team 配置（jackclaw_team/config.yaml）

```yaml
workspace:
  id: jackclaw-team
  name: JackClaw 团队协作

agent:
  model: qwen3.6-max-preview
  max_iter: 30

sandbox:
  url: http://localhost:8029/mcp

team:
  roles: ["manager", "pm", "rd", "qa"]

memory:
  workspace_dir: ./workspace
  ctx_dir: ./data/ctx
```

## 🐳 Docker 服务

### pgvector 向量数据库
```bash
docker compose -f pgvector-docker-compose.yaml up -d
```

### sandbox 沙盒环境
```bash
docker compose -f sandbox-docker-compose.yaml up -d
```

## 📊 监控和日志

### 查看日志
```bash
# JackClaw 日志
tail -f data/logs/jackclaw.log

# 实时监控
tail -f data/logs/*.log
```

### Prometheus Metrics
- JackClaw: http://localhost:9091/metrics
- JackClaw Team: http://localhost:9100/metrics

## 🛠️ 常见问题

### Q: 启动报错 `feishu.app_id / feishu.app_secret 不能为空`
A: 检查 `.env` 文件中的飞书凭证是否正确配置。

### Q: 飞书消息收不到
A:
1. 确认飞书应用已发布
2. 检查权限配置（im:message、im:chat等）
3. 验证 App ID 和 App Secret

### Q: sandbox 连接失败
A: 启动 sandbox 服务 `docker compose -f sandbox-docker-compose.yaml up -d`

### Q: 团队模式角色不响应
A:
1. 检查 `jackclaw_team/config.yaml` 配置
2. 确认 sandbox 服务运行在正确端口（8029）
3. 查看日志中的错误信息

### Q: 内存/性能问题
A:
1. 减少 `session.max_history_turns`
2. 降低 `agent.max_iter`
3. 使用更快的模型（如 qwen-turbo）

## 🔒 安全说明

- `.env` 文件包含敏感信息，已在 `.gitignore` 中排除
- 飞书 App Secret 需要在开放平台重置后使用
- 建议在生产环境使用独立的数据库实例

## 📝 开发指南

### 添加新技能
1. 在 `jackclaw/skills/` 创建新的技能目录
2. 编写 `SKILL.md` 定义技能行为
3. 在 `load_skills.yaml` 中注册技能

### 扩展团队角色
1. 在 `jackclaw_team/workspace/` 创建新角色目录
2. 定义 `agent.md`、`soul.md`、`memory.md`
3. 在 `main.py` 中注册角色

## 📄 License

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
