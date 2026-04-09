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

## 配置项（config.yaml）

```yaml
feishu:
  app_id: "cli_xxxxx"
  app_secret: "xxxxx"

llm:
  provider: "aliyun"  # 或 openai
  api_key: "sk-xxx"
  model: "qwen-turbo"

observability:
  metrics_port: 9091

data_dir: "./data"
```

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