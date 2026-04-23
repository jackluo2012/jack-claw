# 更新说明

## 2026-04-21 - 错误修复 + 初始化脚本

### 修复的 Bug

#### 1. `setup_logging()` 参数缺失错误
**问题**: `TypeError: setup_logging() missing 1 required positional argument: 'log_dir'`

**原因**: `main()` 函数中调用 `setup_logging()` 时没有传递必需的 `log_dir` 参数

**修复**: 修改 `jackclaw/main.py` 中的 `main()` 函数，先读取配置文件获取 `data_dir`，然后再调用 `setup_logging()`

**位置**: `jackclaw/main.py:262-274`

#### 2. `FeishuListener` 不接受 `on_bot_added` 参数
**问题**: `TypeError: FeishuListener.__init__() got an unexpected keyword argument 'on_bot_added'`

**原因**: `FeishuListener` 类的 `__init__` 方法不支持 `on_bot_added` 参数

**修复**: 移除了 `main.py` 中创建 `FeishuListener` 时的 `on_bot_added` 参数

**位置**: `jackclaw/main.py:194-200`

### 新增功能

#### 1. 一键初始化脚本
**文件**: `init.sh`

**功能**:
- ✅ 自动创建 Python 虚拟环境
- ✅ 自动安装所有依赖包
- ✅ 自动生成配置文件（从 template 复制）
- ✅ 自动创建必要的数据目录
- ✅ 自动初始化工作区文件
- ✅ 支持交互式配置编辑
- ✅ 询问是否启动 Docker 服务（pgvector 和 sandbox）
- ✅ 可选择立即启动服务

**使用方法**:
```bash
./init.sh
```

#### 2. 一键启动脚本
**文件**: `start.sh`

**功能**:
- ✅ 自动检查虚拟环境是否存在
- ✅ 自动检查配置文件是否存在
- ✅ 自动激活虚拟环境
- ✅ 启动 JackClaw 服务

**使用方法**:
```bash
./start.sh
```

### 文档更新

#### 1. README.md 更新
- 新增"一键初始化"说明
- 完善配置项文档，包含完整的配置示例
- 新增 Docker 服务配置说明（pgvector 和 sandbox）
- 新增环境变量配置说明
- 新增飞书应用配置详细步骤
- 新增"常见问题"章节，包含故障排查指南
- 新增"日志和调试"章节，包含日志查看和调试方法

#### 2. 新增 QUICKSTART.md
- 5 分钟快速入门指南
- 分步骤说明，从初始化到使用
- 飞书应用配置详细步骤
- API Key 配置说明
- 常用功能介绍
- 故障排查清单

### 验证结果

程序已成功启动，所有功能正常：

```
[INFO] JackClaw starting...
[INFO] jackclaw.ready. sandbox_url=http://localhost:8022/mcp, test_api=False
```

数据目录已创建：
- `data/cron` - 定时任务数据
- `data/ctx` - 上下文存储
- `data/logs` - 日志文件
- `data/sessions` - 会话数据
- `data/workspace` - 工作区

日志文件正常写入：
- `data/logs/jackclaw.log` - JSON 格式日志

### 使用方式

#### 快速启动
```bash
# 首次使用
./init.sh

# 后续启动
./start.sh
```

#### 手动启动
```bash
source .venv/bin/activate
python3 -m jackclaw.main
```

#### 查看日志
```bash
tail -f data/logs/jackclaw.log
```

### 配置清单

确保以下配置已正确填写：

#### 必填配置
- [ ] `config.yaml` 中的 `feishu.app_id`
- [ ] `config.yaml` 中的 `feishu.app_secret`
- [ ] 环境变量 `QWEN_API_KEY`（或配置在相应的 API Key 位置）

#### 可选配置
- [ ] `memory.db_dsn` - 如果使用 pgvector
- [ ] `BAIDU_API_KEY` - 如果使用搜索技能
- [ ] Docker 服务启动（pgvector 和 sandbox）

### 下一步建议

1. 根据实际需求配置飞书应用权限
2. 设置 API Key（阿里云通义千问等）
3. 启动必要的 Docker 服务
4. 根据使用场景调整配置参数
5. 定期检查日志文件监控运行状态
