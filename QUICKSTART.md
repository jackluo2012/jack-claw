# JackClaw 快速入门指南

本指南将帮助你在 5 分钟内启动 JackClaw 并开始使用。

## 前置要求

- Python 3.12+
- Docker（可选，用于 pgvector 和 sandbox 服务）
- 飞书账号

## 第一步：一键初始化

```bash
# 克隆项目
git clone https://github.com/jackluo2012/jack-claw.git
cd jack-claw

# 运行初始化脚本
./init.sh
```

脚本会自动完成：
- ✅ 创建 Python 虚拟环境
- ✅ 安装所有依赖
- ✅ 生成配置文件
- ✅ 创建数据目录
- ✅ 初始化工作区

## 第二步：配置飞书应用

### 2.1 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 点击"创建企业自建应用"
3. 填写应用信息（应用名称、描述等）
4. 创建完成后，在"凭证与基础信息"页面获取：
   - App ID
   - App Secret

### 2.2 配置应用权限

在应用管理页面，添加以下权限：

- `im:message` (获取与发送消息)
- `im:message:group_at_msg` (读取群聊@消息)
- `im:chat` (读取会话信息)
- `drive:drive` (访问文件)

### 2.3 发布应用

1. 在应用管理页面，点击"版本管理与发布"
2. 创建版本，填写版本信息
3. 提交审核（内部使用可直接通过）
4. 发布应用

### 2.4 填写配置文件

编辑 `config.yaml`：

```yaml
feishu:
  app_id: "cli_a95ed6ab497bdbc9"        # 替换为你的 App ID
  app_secret: "your_app_secret_here"    # 替换为你的 App Secret
```

## 第三步：配置 API Key

### 3.1 配置阿里云通义千问 API

1. 访问 [阿里云百炼平台](https://bailian.console.aliyun.com/)
2. 开通服务并获取 API Key
3. 设置环境变量：

```bash
export QWEN_API_KEY="sk-xxx"
```

或者在 `config.yaml` 中配置：

```yaml
agent:
  model: "qwen3-max-preview"  # 或其他支持的模型
```

## 第四步：启动服务

### 4.1 启动 Docker 服务（可选）

```bash
# 启动 pgvector 数据库
docker compose -f pgvector-docker-compose.yaml up -d

# 启动 sandbox 服务
docker compose -f sandbox-docker-compose.yaml up -d
```

### 4.2 启动 JackClaw

```bash
# 使用启动脚本
./start.sh

# 或手动启动
source .venv/bin/activate
python3 -m jackclaw.main
```

看到以下日志表示启动成功：

```
[INFO] JackClaw starting...
[INFO] jackclaw ready. sandbox_url=http://localhost:8022/mcp, test_api=False
```

## 第五步：开始使用

### 5.1 添加机器人到飞书

1. 在飞书应用管理页面，找到"应用概览"
2. 扫描二维码或在应用商店搜索你的应用
3. 添加到飞书（可以发送给好友或在群聊中添加）

### 5.2 发送消息测试

在飞书中向机器人发送消息：

- 简单对话：`你好`
- 询问问题：`今天天气怎么样？`
- 执行任务：`帮我分析一下数据`

### 5.3 查看日志

```bash
# 实时查看日志
tail -f data/logs/jackclaw.log
```

## 常用功能

### 技能（Skills）使用

JackClaw 支持多种技能，可以通过自然语言调用：

- `帮我分析这个 PDF` - PDF 分析技能
- `创建一个 Python 脚本` - 代码生成技能
- `搜索相关信息` - 搜索技能
- `生成图表` - 数据可视化技能

### 定时任务

支持三种定时模式：

```bash
# at 模式：在指定时间执行
at 2025-04-22 09:00 提醒我开会

# every 模式：每隔一段时间执行
every 1h 检查邮件

# cron 模式：使用 cron 表达式
cron "0 9 * * 1-5" 发送晨报
```

### 会话管理

- 会话自动持久化
- 支持多轮对话
- 自动记忆上下文

## 故障排查

### 问题：飞书消息无法接收

**检查清单**：
- ✅ App ID 和 App Secret 是否正确
- ✅ 应用是否已发布
- ✅ 权限是否已配置
- ✅ 网络连接是否正常

### 问题：AI 回复很慢

**优化方案**：
- 检查网络连接
- 尝试切换到更快的模型（如 qwen3-turbo）
- 查看 sandbox 服务是否正常

### 问题：某些功能不可用

**可能原因**：
- Docker 服务未启动
- 配置文件路径错误
- 依赖包未完全安装

## 下一步

- 📖 查看 [README.md](./README.md) 了解完整功能
- 🔧 查看 [docs/](./docs/) 目录了解详细实现
- 💬 加入社区获取帮助

## 获取帮助

- GitHub Issues: https://github.com/jackluo2012/jack-claw/issues
- 查看日志: `tail -f data/logs/jackclaw.log`
- 检查配置: `cat config.yaml`
