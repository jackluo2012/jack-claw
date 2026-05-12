# JackClaw 快速开始指南

5分钟快速启动 JackClaw 飞书智能助手。

## 前置条件

- Python 3.12+
- 飞书账号
- 阿里云百炼 API Key

## 第一步：获取必要凭证

### 1. 飞书应用凭证
1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 在「凭证与基础信息」获取 App ID
4. **重置** App Secret（记录密钥）
5. 添加权限：`im:message`、`im:chat`、`drive:drive`
6. **发布应用**

### 2. 阿里云百炼 API Key
1. 访问 [阿里云百炼控制台](https://bailian.console.aliyun.com/)
2. 获取 API Key

## 第二步：初始化项目

```bash
# 克隆项目
git clone https://github.com/jackluo2012/jack-claw.git
cd jack-claw

# 运行初始化脚本
./init.sh
```

## 第三步：配置环境变量

编辑 `.env` 文件，填入你的凭证：

```bash
# 飞书凭证
FEISHU_APP_ID=cli_a1b2c3d4e5f6g7h8
FEISHU_APP_SECRET=your_app_secret_here

# 阿里云百炼
QWEN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
```

## 第四步：选择模式并启动

### 模式 A：个人助手（推荐新手）

```bash
./start.sh
```

看到 `jackclaw ready` 表示启动成功！

### 模式 B：团队协作（高级用户）

```bash
source .venv/bin/activate
python3 -m jackclaw_team.main
```

## 第五步：在飞书中测试

1. 在飞书中找到你的应用
2. 发送私聊消息：`你好`
3. 等待 AI 回复

## 常见问题快速修复

### 问题：飞书收不到消息
```bash
# 检查应用是否已发布
# 检查权限是否正确配置
# 查看日志：tail -f data/logs/jackclaw.log
```

### 问题：启动失败
```bash
# 检查 Python 版本
python3 --version  # 应该是 3.12+

# 重新初始化
rm -rf .venv
./init.sh
```

### 问题：API 调用失败
```bash
# 验证 API Key
echo $QWEN_API_KEY

# 检查网络连接
curl https://dashscope.aliyuncs.com
```

## 下一步

- 📖 阅读完整文档：[docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- 🔧 查看配置说明：[README.md](README.md)
- 🚀 启用高级功能：Docker 服务、自定义技能等

## 停止服务

```bash
# Ctrl+C 或
./stop.sh
```

## 获取帮助

- 📋 [完整文档](docs/USER_GUIDE.md)
- 🐛 [问题反馈](https://github.com/jackluo2012/jack-claw/issues)
- 💬 [社区讨论](https://github.com/jackluo2012/jack-claw/discussions)
