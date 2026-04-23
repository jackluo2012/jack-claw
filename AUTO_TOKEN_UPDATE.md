# 自动 Token 配置更新功能

## 功能说明

每次执行 `start.sh` 时，脚本会自动检测配额文件，并将最大 Token 的模型配置更新到 `config.yaml` 中。

## 使用方法

### 方法 1: 默认路径（推荐）

将你的配额 JSON 文件保存为 `quota.json`，放在项目根目录：

```bash
cp 你的配额文件.json quota.json
./start.sh
```

### 方法 2: 自定义路径

通过环境变量指定配额文件路径：

```bash
export QUOTA_FILE=/path/to/your/quota.json
./start.sh
```

### 方法 3: 一次性使用

```bash
QUOTA_FILE=/path/to/quota.json ./start.sh
```

## 手动更新配置

如果需要在不启动服务的情况下更新配置：

```bash
# 更新 config.yaml
python set_max_token.py quota.json --update-config

# 生成环境变量
eval $(python set_max_token.py quota.json)

# 写入 .env 文件
python set_max_token.py quota.json --env .env
```

## 配额文件格式

配额文件应该是阿里云 API 返回的 JSON 格式，包含 `freeTierQuotas` 数组。

示例文件已提供：`quota_example.json`

## 更新内容

脚本会自动更新 `config.yaml` 中的以下配置：

1. **agent.model**: 最大 Token 的模型名称
2. **agent.max_input_tokens**: 最大输入 Token（配额的 80%）
3. **agent.sub_agent_model**: 子代理模型（使用相同的最大模型）

## 注意事项

- 只有配额状态为 `VALID` 的模型才会被考虑
- 如果配额文件不存在或格式错误，会跳过更新并使用现有配置
- 建议定期更新配额文件以获取最新的配额信息

## 工作流程

1. 启动时检测 `quota.json` 或 `$QUOTA_FILE` 指定的文件
2. 解析 JSON，找到 `quotaTotal` 最大的有效模型
3. 更新 `config.yaml` 中的相关配置
4. 启动 JackClaw 服务

## 测试

运行测试脚本验证功能：

```bash
./test_quota_update.sh
```
