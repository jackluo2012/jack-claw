# JackClaw

飞书本地工作助手

## 功能特性

- **飞书消息接收** - WebSocket 长连接接收私聊/群聊/thread 消息
- **消息分发** - 按 routing_key（p2p/group/thread）分队列处理
- **Agent 对话** - 支持多轮对话、会话持久化
- **Skills 系统** - 动态加载外部技能（pdf/xlsx/docx 等）
- **沙盒执行** - 本地安全执行 Python/Bash 脚本
- **定时任务** - 支持 at/every/cron 三种调度模式
- **可观测性** - Prometheus metrics 暴露（端口 9091）

## 快速开始

### 1. 克隆并初始化

```bash
git clone https://github.com/jackluo2012/jack-claw.git
cd jack-claw
./init.sh
```

### 2. 填写 .env（所有密钥统一在此文件）

```bash
# 飞书开放平台 https://open.feishu.cn/ → 应用 → 凭证与基础信息
FEISHU_APP_ID=cli_a95ed6ab497bdbc9
FEISHU_APP_SECRET=<重置后填入新值>

# 阿里云百炼 https://bailian.console.aliyun.com/
QWEN_API_KEY=<填入你的 API Key>

# 百度千帆（baidu_search skill 用）
BAIDU_API_KEY=<填入你的 API Key>

# pgvector 连接串（本地没有 pgvector 则留空）
MEMORY_DB_DSN=postgresql://user:pass@localhost:5432/jackclaw_memory
```

> **注意**：`.env` 不入 Git（已在 `.gitignore`），敏感密钥只存在这里。

### 3. 启动服务

```bash
./start.sh
# 或
source .venv/bin/activate
python3 -m jackclaw.main
```

看到日志 `jackclaw ready` 即启动成功。

### 4. 启动 Docker 服务（可选）

```bash
# pgvector 向量数据库
docker compose -f pgvector-docker-compose.yaml up -d

# sandbox 安全沙盒
docker compose -f sandbox-docker-compose.yaml up -d
```

---

## 配置说明

### 敏感密钥 → `.env`

所有密钥统一写在项目根目录的 `.env` 文件，由 `config.py` 在启动时自动加载。

| 变量 | 说明 |
|------|------|
| `FEISHU_APP_ID` | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | 飞书 App Secret（需在开放平台重置） |
| `QWEN_API_KEY` | 阿里云百炼 API Key |
| `BAIDU_API_KEY` | 百度千帆 API Key |
| `MEMORY_DB_DSN` | pgvector 连接串（有 pgvector 时必填） |

### config.yaml → 非敏感配置

`config.yaml` 中的 `${VAR}` 和 `${VAR:-default}` 会被替换为 `.env` 中对应的环境变量值。

```yaml
feishu:
  app_id: ${FEISHU_APP_ID}
  app_secret: ${FEISHU_APP_SECRET}

baidu:
  api_key: ${BAIDU_API_KEY:-}

memory:
  db_dsn: ${MEMORY_DB_DSN:-}

sandbox:
  url: "http://localhost:8022/mcp"

agent:
  model: qwen3-max
```

### LLM 配置（llm_config.yaml）

模型白名单和多 Provider 管理，API Key 从环境变量读取：

```yaml
providers:
  aliyun:
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: QWEN_API_KEY
    models:
      - qwen-max
      - qwen-plus
      - qwen-turbo
```

---

## 飞书应用配置

1. 访问 [飞书开放平台](https://open.feishu.cn/)，创建企业自建应用
2. 在「凭证与基础信息」获取 App ID，**重置 App Secret**（旧的已清理）
3. 添加权限：`im:message`、`im:message:group_at_msg`、`im:chat`、`drive:drive`
4. 发布应用

---

## 项目结构

```
jack-claw/
├── .env                    ← 所有密钥在这里（不入 Git）
├── config.yaml             ← 非敏感配置，使用 ${VAR} 引用 .env
├── jackclaw/
│   ├── main.py             ← 入口
│   ├── config.py            ← 配置加载 + 自动加载 .env
│   ├── feishu/              ← 飞书监听/发送
│   ├── session/             ← 会话管理
│   ├── llm/                 ← LLM 适配器 + llm_config.yaml
│   ├── agents/              ← Agent 实现
│   ├── skills/              ← 技能
│   └── sandbox/             ← 沙盒执行
├── data/                   ← 工作区、上下文、日志
├── init.sh                 ← 一键初始化
└── start.sh                ← 一键启动
```

---

## 常见问题

**Q: 启动报错 `feishu.app_id / feishu.app_secret 不能为空`**
A: `.env` 中 `FEISHU_APP_SECRET` 是占位符，需在飞书开放平台重置后填入新值。

**Q: 飞书消息收不到**
A: 检查 App ID / App Secret 是否正确，应用是否已发布，权限是否配置。

**Q: sandbox 连接失败**
A: `docker compose -f sandbox-docker-compose.yaml up -d`

**Q: pgvector 连接失败**
A: `docker compose -f pgvector-docker-compose.yaml up -d`，确认 `MEMORY_DB_DSN` 填入 `.env`。

**Q: AI 回复很慢**
A: 检查网络，或切换到更快模型（如 `qwen3-turbo`）。

---

## 日志

```bash
tail -f data/logs/jackclaw.log
```
