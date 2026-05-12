# JackClaw 项目概览

## 项目简介

JackClaw 是一个基于飞书的智能工作助手系统，通过 AI 技术为个人和团队提供智能协作能力。

## 核心模块

### 1. JackClaw（个人助手）

**定位**: 面向个人的智能助手，提供对话、技能调用、任务管理等功能。

**核心功能**:
- 🤖 **智能对话**: 基于大语言模型的多轮对话
- 📥 **飞书集成**: WebSocket 实时消息接收和处理
- 🛠️ **技能系统**: 动态加载外部技能（PDF/Excel/Word/搜索等）
- 🔒 **安全沙盒**: 隔离环境执行 Python/Bash 代码
- ⏰ **定时任务**: 支持 cron 表达式的定时调度
- 📊 **可观测性**: Prometheus metrics 监控

**技术栈**:
- **LLM**: 阿里云百炼 (Qwen 系列)
- **消息**: 飞书 WebSocket API
- **沙盒**: Docker 容器隔离
- **监控**: Prometheus + 自定义 metrics
- **数据库**: pgvector (可选，用于语义检索)

**目录结构**:
```
jackclaw/
├── main.py              # 入口文件
├── config.py            # 配置管理
├── feishu/              # 飞书集成
│   ├── listener.py      # 消息监听
│   ├── sender.py        # 消息发送
│   └── downloader.py    # 文件下载
├── llm/                 # LLM 适配器
│   ├── aliyun_llm.py    # 阿里云 LLM
│   └── factory.py       # LLM 工厂
├── agents/              # Agent 实现
│   └── main_crew.py     # CrewAI Agent
├── skills/              # 技能系统
│   └── load_skills.yaml # 技能配置
├── sandbox/             # 沙盒客户端
├── session/             # 会话管理
├── cron/                # 定时任务
└── observability/       # 监控和日志
```

**运行方式**:
```bash
./start.sh
# 或
python3 -m jackclaw.main
```

**配置文件**: `config.yaml`

**端口使用**:
- 9091: Prometheus metrics

---

### 2. JackClaw Team（团队协作）

**定位**: 面向团队的 AI 协作平台，模拟真实软件团队的工作流程。

**核心功能**:
- 👥 **多角色协作**: Manager/PM/RD/QA 四个专业 AI 角色
- 📧 **邮箱系统**: 角色间异步通讯和任务分发机制
- 🔄 **自动工作流**: 需求→设计→开发→测试的完整 SOP 流程
- 💓 **心跳机制**: 定期检查和处理待办事项（30s 间隔）
- 📁 **项目管理**: 完整的项目生命周期管理
- 🎯 **检查点**: 关键决策点人工确认机制

**角色说明**:

| 角色 | 英文名 | 职责 |
|------|--------|------|
| 项目经理 | Manager | 需求澄清、任务分配、验收协调、检查点管理 |
| 产品经理 | PM | 产品设计、需求文档、验收标准制定 |
| 研发工程师 | RD | 技术设计、代码实现、单元测试 |
| 质量保证 | QA | 测试设计、质量保证、缺陷报告 |

**工作流程**:
```
用户需求
   ↓
Manager (澄清需求、创建项目)
   ↓
PM (产品设计 product_spec.md)
   ↓
RD (技术设计 tech_design.md + 代码实现)
   ↓
QA (测试设计 + 测试执行)
   ↓
Manager (验收 + 交付用户)
```

**技术特点**:
- **邮箱机制**: 基于 JSON 文件的异步通讯系统
- **事件溯源**: events.jsonl 记录所有项目事件
- **共享工作区**: 角色间共享项目文件和上下文
- **Cron 集成**: 定时触发角色心跳和任务检查
- **SOP 引擎**: 基于 Markdown 的标准作业程序

**目录结构**:
```
jackclaw_team/
├── main.py              # 入口文件
├── runner.py            # 消息分发器
├── agents/              # Agent 构建器
├── workspace/           # 工作空间
│   ├── manager/         # Manager 工作区
│   │   ├── agent.md     # 角色定义
│   │   ├── soul.md      # 个性特征
│   │   ├── memory.md    # 记忆配置
│   │   └── skills/      # 专属技能
│   ├── pm/              # PM 工作区
│   ├── rd/              # RD 工作区
│   ├── qa/              # QA 工作区
│   └── shared/          # 共享项目空间
│       └── projects/    # 项目目录
│           ├── <ID>/
│           │   ├── needs/        # 需求文档
│           │   ├── design/       # 设计文档
│           │   ├── tech/         # 技术文档
│           │   ├── code/         # 代码实现
│           │   ├── qa/           # 测试文档
│           │   ├── reviews/      # 评审文档
│           │   ├── mailboxes/    # 角色邮箱
│           │   └── events.jsonl  # 事件日志
├── cron/                # 定时任务
│   └── tasks.json       # 任务配置
└── feishu/              # 飞书集成
```

**运行方式**:
```bash
# 完整模式（含飞书）
python3 -m jackclaw_team.main

# 仅 Cron 模式
python3 -m jackclaw_team.main --no-feishu
```

**配置文件**: `jackclaw_team/config.yaml`

**端口使用**:
- 8029: Team 沙盒服务
- 9100: Prometheus metrics

---

## 通用组件

### 配置管理
- **环境变量**: `.env` 文件存储敏感信息
- **配置文件**: YAML 格式的非敏感配置
- **动态加载**: 支持 `${VAR}` 语法引用环境变量

### LLM 集成
- **阿里云百炼**: 主要 LLM 提供商
- **模型支持**: qwen-max, qwen-plus, qwen-turbo, qwen3.6-max-preview
- **多 Provider**: 支持扩展其他 LLM 提供商

### 沙盒执行
- **Docker 隔离**: 安全的代码执行环境
- **多语言支持**: Python、Bash 等
- **文件系统隔离**: 独立的 workspace 目录
- **超时控制**: 防止长时间运行

### 数据存储
- **会话持久化**: JSON 格式的会话历史
- **文件存储**: 本地文件系统
- **向量数据库**: pgvector (可选)

### 监控和日志
- **结构化日志**: JSON 格式日志输出
- **Prometheus**: 指标收集和暴露
- **健康检查**: HTTP 健康检查端点

---

## 对比总结

| 特性 | JackClaw | JackClaw Team |
|------|----------|---------------|
| **用户类型** | 个人 | 团队 |
| **AI 角色** | 1 个助手角色 | 4 个专业角色 |
| **交互方式** | 直接对话 | 邮箱系统 + 检查点 |
| **任务流程** | 线性处理 | 完整软件生命周期 |
| **适用场景** | 日常助手、文档处理 | 项目开发、团队协作 |
| **复杂度** | 简单 | 高 |
| **学习成本** | 低 | 中高 |
| **沙盒端口** | 8022 | 8029 |
| **Metrics 端口** | 9091 | 9100 |

---

## 技术架构

### 消息流
```
飞书/用户
   ↓
Listener (WebSocket)
   ↓
Runner (消息分发)
   ↓
Agent (AI 处理)
   ↓
Skills/Tools (技能/工具)
   ↓
Sender (消息发送)
   ↓
飞书/用户
```

### 并发模型
- **asyncio**: 异步 I/O 处理
- **队列系统**: 消息队列防止并发冲突
- **锁机制**: 团队模式使用 asyncio.Lock 防止串台

### 扩展性
- **技能插件**: 动态加载外部技能
- **角色扩展**: 可添加新的 AI 角色
- **Provider 扩展**: 支持多种 LLM 提供商
- **消息源扩展**: 可集成其他通讯平台

---

## 开发和贡献

### 本地开发
```bash
# 安装依赖
./init.sh

# 运行测试
pytest

# 代码格式化
black jackclaw/ jackclaw_team/

# 类型检查
mypy jackclaw/ jackclaw_team/
```

### 添加技能
1. 在 `jackclaw/skills/` 创建技能目录
2. 编写 `SKILL.md` 定义行为
3. 在 `load_skills.yaml` 中注册

### 扩展角色
1. 在 `jackclaw_team/workspace/` 创建角色目录
2. 定义 `agent.md`、`soul.md`、`memory.md`
3. 在 `main.py` 中注册

---

## 相关链接

- **GitHub**: https://github.com/jackluo2012/jack-claw
- **飞书开放平台**: https://open.feishu.cn/
- **阿里云百炼**: https://bailian.console.aliyun.com/
- **CrewAI**: https://www.crewai.com/

---

## 许可证

MIT License

---

## 联系方式

- **Issue**: https://github.com/jackluo2012/jack-claw/issues
- **Discussion**: https://github.com/jackluo2012/jack-claw/discussions
