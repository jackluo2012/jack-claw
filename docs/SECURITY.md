# JackClaw 密钥管理安全指南

## 📋 目录
- [架构概述](#架构概述)
- [配置流程](#配置流程)
- [安全机制](#安全机制)
- [常见问题](#常见问题)
- [最佳实践](#最佳实践)

## 架构概述

JackClaw 采用**集中式密钥管理架构**，所有敏感信息通过统一入口管理：

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   .env      │ ───► │  config.py   │ ───► │  应用代码    │
│ (密钥存储)   │      │  (统一加载)   │      │  (使用配置)  │
└─────────────┘      └──────────────┘      └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ config.yaml  │
                    │ (配置模板)    │
                    └──────────────┘
```

### 核心原则

1. **单一真相源**：所有密钥只在 `.env` 中定义一次
2. **统一加载**：`config.py` 在模块加载时自动读取 `.env`
3. **环境变量传递**：通过 `config.yaml` 的 `${VAR}` 语法引用
4. **不直接访问**：代码中不直接调用 `os.environ.get()`

## 配置流程

### 1. 初始化配置

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置文件，填入你的密钥
vim .env
```

### 2. 配置文件说明

#### `.env`（密钥存储）
```bash
# 只在这里填写真实的密钥值
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=your_secret_here
QWEN_API_KEY=your_qwen_key
BAIDU_API_KEY=your_baidu_key
```

#### `config.yaml`（配置模板）
```yaml
# 使用环境变量占位符，不直接写密钥
feishu:
  app_id: ${FEISHU_APP_ID}
  app_secret: ${FEISHU_APP_SECRET}

baidu:
  api_key: ${BAIDU_API_KEY:-}  # :- 表示可选，空值时为空字符串
```

### 3. 运行时加载流程

1. **程序启动** → `config.py` 模块被导入
2. **自动加载** → `_find_dotenv()` 查找并加载 `.env`
3. **环境变量** → `load_dotenv()` 将密钥加载到 `os.environ`
4. **配置解析** → `load_config()` 读取 `config.yaml`
5. **变量替换** → `_expand_env_vars()` 将 `${VAR}` 替换为实际值
6. **应用使用** → 代码通过 `cfg.get()` 获取配置

## 安全机制

### 1. 文件系统保护

- **`.env` 权限**：建议设置为 `600`（仅属主可读写）
- **沙盒配置**：`data/workspace/.config/*.json` 权限为 `600`
- **Git 保护**：`.env` 和 `config.yaml` 已加入 `.gitignore`

### 2. 访问控制

```python
# ✅ 正确：通过配置对象访问
from jackclaw.config import load_config
cfg = load_config()
app_secret = cfg.get("feishu", {}).get("app_secret")

# ❌ 错误：直接访问环境变量
import os
app_secret = os.environ.get("FEISHU_APP_SECRET")  # 不推荐
```

### 3. 日志脱敏

```python
# 诊断脚本中自动隐藏敏感信息
print(f"App Secret: {'*' * 10} (已隐藏)")
```

### 4. 沙盒隔离

沙盒进程需要访问 API 密钥时，通过以下安全方式传递：

1. 主进程从 `.env` 加载密钥
2. 写入 `data/workspace/.config/` 目录
3. 文件权限设置为 `0o600`
4. 沙盒进程从本地文件读取（不经过 LLM）

## 常见问题

### Q1: 为什么密钥还在日志中显示？

**A**: 检查是否有代码直接输出密钥。使用检查工具排查：

```bash
python scripts/check_env.py
```

### Q2: 如何在 Docker 中使用？

**A**: 使用 Docker secrets 或环境变量：

```dockerfile
# 方式1：通过 env_file
docker run --env-file .env your-image

# 方式2：通过 docker secrets（推荐）
docker service create \
  --secret source=feishu_secret,target=feishu_secret \
  your-image
```

### Q3: 生产环境如何管理密钥？

**A**: 推荐方案：

1. **云平台**：使用 AWS Secrets Manager / Azure Key Vault
2. **K8s**：使用 Kubernetes Secrets
3. **自托管**：使用 HashiCorp Vault

示例（Kubernetes）：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: jackclaw-secrets
type: Opaque
stringData:
  FEISHU_APP_ID: "cli_xxx"
  FEISHU_APP_SECRET: "your_secret"
---
apiVersion: v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: jackclaw
        envFrom:
        - secretRef:
            name: jackclaw-secrets
```

### Q4: 如何验证配置是否安全？

**A**: 运行安全检查：

```bash
# 检查密钥配置
python scripts/check_env.py

# 检查文件权限
ls -la .env
ls -la data/workspace/.config/

# 检查 Git 状态（确保没有误提交）
git status
git log --all --full-history -- "*.env"
```

## 最佳实践

### 开发环境

1. ✅ 使用 `.env` 文件存储密钥
2. ✅ 定期运行 `python scripts/check_env.py` 检查
3. ✅ 确保 `.env` 权限为 `600`
4. ✅ 不要在代码中硬编码密钥

### 生产环境

1. ✅ 使用专业的密钥管理服务
2. ✅ 定期轮换 API 密钥
3. ✅ 启用审计日志
4. ✅ 使用不同的密钥用于不同环境

### 代码审查清单

- [ ] 没有硬编码的密钥
- [ ] 没有直接调用 `os.environ.get()`（除非在 `config.py` 中）
- [ ] 日志中没有输出敏感信息
- [ ] `.env` 在 `.gitignore` 中
- [ ] 沙盒配置文件权限正确

## 安全更新日志

### 2026-04-27
- ✅ 修复 `diagnose_feishu.py` 中密钥泄露问题
- ✅ 移除 `main.py` 中直接访问环境变量的代码
- ✅ 更新 `.gitignore` 保护沙盒配置文件
- ✅ 添加密钥配置检查工具
- ✅ 改进错误处理和日志记录

## 相关文件

- `jackclaw/config.py` - 配置加载逻辑
- `config.yaml` - 配置模板
- `.env.example` - 环境变量示例
- `scripts/check_env.py` - 安全检查工具
- `.gitignore` - Git 忽略规则

---

**⚠️ 重要提示**：如果你怀疑密钥已泄露，请立即：
1. 在对应平台重置密钥
2. 更新 `.env` 文件
3. 检查访问日志是否有异常
4. 考虑启用密钥轮换机制
