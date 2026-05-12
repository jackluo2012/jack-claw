# JackClaw 运行指南

## 目录
- [环境准备](#环境准备)
- [JackClaw 个人助手模式](#jackclaw-个人助手模式)
- [JackClaw Team 团队协作模式](#jackclaw-team-团队协作模式)
- [配置详解](#配置详解)
- [故障排查](#故障排查)

## 环境准备

### 系统要求
- Linux/macOS/WSL2
- Python 3.12 或更高版本
- Docker & Docker Compose（可选，用于高级功能）

### 依赖安装

1. **克隆项目**
```bash
git clone https://github.com/jackluo2012/jack-claw.git
cd jack-claw
```

2. **运行初始化脚本**
```bash
./init.sh
```

初始化脚本会自动完成：
- 创建 Python 虚拟环境 (`.venv`)
- 安装项目依赖
- 生成配置文件模板
- 创建必要的数据目录

3. **配置环境变量**

复制并编辑 `.env` 文件：
```bash
cp .env.example .env
vi .env  # 或使用你喜欢的编辑器
```

必填项：
```bash
# 飞书开放平台凭证
FEISHU_APP_ID=cli_a1b2c3d4e5f6g7h8
FEISHU_APP_SECRET=your_app_secret_here

# 阿里云百炼 API Key
QWEN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
```

可选项：
```bash
# 百度千帆 API Key（搜索功能需要）
BAIDU_API_KEY=your_baidu_api_key

# pgvector 数据库连接串（语义检索需要）
MEMORY_DB_DSN=postgresql://user:pass@localhost:5432/jackclaw
```

## JackClaw 个人助手模式

### 功能特点
- 🤖 **智能对话**: 基于大语言模型的多轮对话
- 📥 **飞书集成**: 实时接收和处理飞书消息
- 🛠️ **技能系统**: 支持文档处理、网络搜索等扩展功能
- 🔒 **安全沙盒**: 隔离环境执行代码
- ⏰ **定时任务**: 支持 cron 表达式的定时任务

### 启动步骤

1. **确认配置正确**
```bash
cat config.yaml
```

2. **启动服务**
```bash
# 方式一：使用启动脚本
./start.sh

# 方式二：手动启动
source .venv/bin/activate
python3 -m jackclaw.main
```

3. **验证运行状态**
```bash
# 查看日志
tail -f data/logs/jackclaw.log

# 检查进程
ps aux | grep jackclaw

# 测试 metrics 端点
curl http://localhost:9091/metrics
```

### 使用示例

#### 基础对话
在飞书中给机器人发送私聊消息：
```
你好，请帮我分析这个数据...
```

#### 技能调用
```
请搜索最新的人工智能进展
请帮我总结这个 PDF 文件
```

#### 定时任务
```
每天早上 9 点提醒我开会
每小时检查一次邮件
```

### 停止服务
```bash
# 方式一：使用停止脚本
./stop.sh

# 方式二：手动停止
kill $(cat .jackclaw.pid)
```

## JackClaw Team 团队协作模式

### 功能特点
- 👥 **多角色协作**: Manager/PM/RD/QA 四个专业角色
- 📧 **邮箱系统**: 角色间异步通讯和任务分发
- 🔄 **自动工作流**: 需求→设计→开发→测试的完整流程
- 💓 **心跳机制**: 定期检查和处理待办事项
- 📁 **项目管理**: 完整的项目生命周期管理

### 角色说明

| 角色 | 职责 |
|------|------|
| **Manager** | 项目管理、需求澄清、任务分配、验收协调 |
| **PM** | 产品设计、需求文档、验收标准 |
| **RD** | 技术设计、代码实现、单元测试 |
| **QA** | 测试设计、质量保证、缺陷报告 |

### 启动步骤

1. **确认团队配置**
```bash
cat jackclaw_team/config.yaml
```

2. **启动团队模式**
```bash
# 完整模式（含飞书集成）
source .venv/bin/activate
python3 -m jackclaw_team.main

# 仅 Cron 模式（不启动飞书监听）
source .venv/bin/activate
python3 -m jackclaw_team.main --no-feishu
```

3. **验证运行状态**
```bash
# 查看日志
tail -f data/logs/jackclaw.log

# 检查工作空间
ls -la jackclaw_team/workspace/
```

### 使用示例

#### 发起新项目
在飞书中发送：
```
请帮我开发一个用户登录功能
```

Manager 会自动：
1. 澄清需求细节
2. 创建项目空间
3. 分配任务给 PM

#### 查看项目状态
```
查看项目 xxx 的状态
```

#### 团队协作流程
```
用户 → Manager（澄清需求）
     ↓
   PM（产品设计）
     ↓
   RD（技术设计+开发）
     ↓
   QA（测试验证）
     ↓
Manager（验收交付）
     ↓
   用户
```

## 配置详解

### JackClaw 配置文件

```yaml
workspace:
  id: jackclaw-default        # 工作空间 ID
  name: JackClaw 个人助手     # 工作空间名称

feishu:
  app_id: ${FEISHU_APP_ID}           # 飞书 App ID
  app_secret: ${FEISHU_APP_SECRET}   # 飞书 App Secret

agent:
  model: qwen-turbo-1101     # 使用的模型
  max_iter: 50               # 最大迭代次数
  max_input_tokens: 30000    # 最大输入 token 数
  timeout_s: 300            # 超时时间（秒）

sandbox:
  url: http://localhost:8022/mcp  # 沙盒服务地址
  timeout_s: 120                   # 沙盒超时时间
  max_retries: 2                   # 最大重试次数

memory:
  workspace_dir: ./data/workspace  # 工作空间目录
  ctx_dir: ./data/ctx              # 上下文目录
  db_dsn: ${MEMORY_DB_DSN:-}       # 数据库连接串

session:
  max_history_turns: 20    # 最大历史轮数
```

### JackClaw Team 配置文件

```yaml
workspace:
  id: jackclaw-team
  name: JackClaw 团队协作

feishu:
  app_id: ${FEISHU_APP_ID}
  app_secret: ${FEISHU_APP_SECRET}

agent:
  model: qwen3.6-max-preview  # 推荐使用更强模型
  max_iter: 30

sandbox:
  url: http://localhost:8029/mcp  # 注意端口不同

team:
  roles: ["manager", "pm", "rd", "qa"]

memory:
  workspace_dir: ./workspace  # 团队共享工作空间
  ctx_dir: ./data/ctx
```

## 故障排查

### 常见问题

#### 1. 飞书连接失败
**症状**: `飞书连接失败` 或 `认证失败`

**解决方案**:
```bash
# 检查配置
echo $FEISHU_APP_ID
echo $FEISHU_APP_SECRET

# 验证网络连接
curl https://open.feishu.cn

# 查看详细日志
tail -f data/logs/jackclaw.log | grep -i feishu
```

#### 2. 沙盒连接失败
**症状**: `沙盒执行失败` 或 `连接超时`

**解决方案**:
```bash
# 检查 Docker 容器状态
docker ps | grep sandbox

# 重启沙盒服务
docker compose -f sandbox-docker-compose.yaml restart

# 测试沙盒连接
curl http://localhost:8022/mcp
```

#### 3. 模型调用失败
**症状**: `LLM 调用失败` 或 `API 错误`

**解决方案**:
```bash
# 检查 API Key
echo $QWEN_API_KEY

# 测试 API 连接
curl -H "Authorization: Bearer $QWEN_API_KEY" \
  https://dashscope.aliyuncs.com/api/v1/models

# 查看配额使用情况
cat quota.json
```

#### 4. 内存不足
**症状**: 系统变慢或 OOM

**解决方案**:
```bash
# 减少历史轮数
# 编辑 config.yaml
session:
  max_history_turns: 10  # 从 20 降到 10

# 降低最大迭代数
agent:
  max_iter: 25  # 从 50 降到 25

# 使用更快的模型
agent:
  model: qwen-turbo  # 从 qwen-max 降到 qwen-turbo
```

#### 5. 团队角色不响应
**症状**: 某个角色没有反应

**解决方案**:
```bash
# 检查角色配置
ls -la jackclaw_team/workspace/

# 查看特定角色的日志
grep "manager" data/logs/jackclaw.log
grep "rd" data/logs/jackclaw.log

# 检查邮箱状态
ls -la jackclaw_team/workspace/shared/projects/*/mailboxes/
```

### 调试技巧

#### 启用调试日志
```bash
export JACKCLAW_LOG_LEVEL=DEBUG
./start.sh
```

#### 测试 API 端点
```bash
# 检查 metrics
curl http://localhost:9091/metrics

# 健康检查
curl http://localhost:9090/health
```

#### 查看会话状态
```bash
# 列出所有会话
ls -la data/sessions/

# 查看特定会话
cat data/sessions/session_*.json | jq .
```

#### 重置项目状态
```bash
# 清理会话
rm -rf data/sessions/*

# 清空工作空间（谨慎操作）
rm -rf data/workspace/*

# 重新初始化
./init.sh
```

### 性能优化

#### 加速启动
```yaml
# config.yaml
agent:
  model: qwen-turbo  # 使用更快的模型
  max_iter: 20       # 减少迭代次数

session:
  max_history_turns: 10  # 减少历史轮数
```

#### 减少资源占用
```yaml
# 禁用不需要的功能
debug:
  enable_test_api: false

observability:
  enable_metrics: false  # 禁用 metrics 收集
```

#### 优化数据库查询
```yaml
memory:
  db_dsn: ""  # 如果不需要语义检索，留空
```

## 高级用法

### 自定义技能
1. 在 `jackclaw/skills/` 创建新技能目录
2. 编写 `SKILL.md` 定义技能行为
3. 在 `load_skills.yaml` 中注册

### 扩展团队角色
1. 在 `jackclaw_team/workspace/` 创建新角色目录
2. 定义角色配置文件
3. 在 `jackclaw_team/main.py` 中注册

### 集成外部系统
- 修改 `feishu/listener.py` 添加其他消息源
- 扩展 `sender.py` 支持更多通讯渠道
- 自定义 `agents/` 实现特定业务逻辑

## 获取帮助

- 📖 查看日志: `tail -f data/logs/jackclaw.log`
- 🐛 报告问题: https://github.com/jackluo2012/jack-claw/issues
- 💬 讨论: https://github.com/jackluo2012/jack-claw/discussions
