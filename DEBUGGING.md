# 调试指南

本文档记录了 JackClaw 项目调试过程中的常见问题和解决方案。

## 🔧 环境配置问题

### 1. schema.sql 文件缺失
**问题**: pgvector 容器启动时无法找到初始化脚本
**解决方案**:
```bash
# 从 jackclaw_team 复制 schema.sql 到正确位置
cp jackclaw_team/schema.sql schema.sql/
# 修复权限（如果需要）
chmod 644 schema.sql/schema.sql
```

### 2. 环境变量未展开
**问题**: 配置文件中的 `${FEISHU_APP_ID}` 等变量未被正确替换
**解决方案**: 确保 `jackclaw_team/main.py` 中包含环境变量展开逻辑：
```python
def load_config(config_path: Path) -> dict[str, Any]:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return _expand_env_vars(data)

def _expand_env_vars(obj):
    if isinstance(obj, str):
        if obj.startswith("${") and obj.endswith("}"):
            inner = obj[2:-1]
            if ":-" in inner:
                var_name, _, default = inner.partition(":-")
                return os.environ.get(var_name, default)
            return os.environ.get(inner, "")
        return obj
    elif isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars(item) for item in obj]
    return obj
```

## 🌐 WebSocket 连接问题

### 1. 事件循环冲突 "This event loop is already running"
**问题**: lark-oapi 库在已运行的事件循环中尝试启动新的事件循环
**解决方案**:
- 延迟导入 lark-oapi 模块到新线程中
- 在新线程中创建新的事件循环
- 确保在主事件循环启动前预加载相关模块

```python
# 在 main.py 开头预加载
try:
    from lark_oapi.ws import client as ws_client_module
except ImportError:
    pass

# 在 FeishuListener 中延迟导入
def _run_ws_client(self) -> None:
    import asyncio
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)

    from lark_oapi.ws import Client as WSClient
    from lark_oapi.ws.client import EventDispatcherHandler
    # ... 创建和使用 WSClient
```

### 2. WebSocket 连接失败
**检查项**:
1. 飞书应用是否已发布
2. App ID 和 App Secret 是否正确
3. 网络连接是否正常
4. 飞书开放平台权限是否正确配置

## 🤖 LLM API 问题

### 1. 403 错误 "AllocationQuota.FreeTierOnly"
**问题**: 阿里云百炼免费额度已用尽
**解决方案**:
1. 访问[阿里云百炼控制台](https://bailian.console.aliyun.com/)
2. 找到模型配置
3. 关闭"仅使用免费额度"模式
4. 或升级到付费版本

### 2. AliyunLLM 对象缺少方法
**问题**: `'AliyunLLM' object has no attribute 'supports_function_calling'`
**解决方案**: 检查 `AliyunLLM` 类是否实现了 CrewAI 要求的所有方法：
```python
class AliyunLLM:
    def supports_function_calling(self):
        return True  # 或根据实际情况返回
```

## 🐳 Docker 服务问题

### 1. pgvector 容器无法启动
**检查步骤**:
```bash
# 检查容器状态
docker compose -f pgvector-docker-compose.yaml ps

# 查看日志
docker compose -f pgvector-docker-compose.yaml logs

# 检查端口占用
netstat -an | grep 5433
```

### 2. sandbox 容器连接失败
**检查步骤**:
```bash
# 测试连接
curl http://localhost:8022/mcp

# 查看容器日志
docker compose -f sandbox-docker-compose.yaml logs -f

# 检查环境变量是否正确传递
docker compose -f sandbox-docker-compose.yaml config
```

## 🔍 调试技巧

### 1. 启用详细日志
```bash
export JACKCLAW_LOG_LEVEL=DEBUG
python -m jackclaw.main
```

### 2. 检查飞书连接状态
```bash
# 在日志中查找连接成功消息
grep -i "connected" data/logs/*.log
```

### 3. 监控进程状态
```bash
# 实时监控内存和 CPU
watch -n 1 'ps aux | grep python | grep jackclaw'

# 检查文件描述符
lsof -p <pid> | grep -E "socket|file"
```

### 4. 测试单独组件
```bash
# 仅测试 cron 模式
python -m jackclaw_team.main --no-feishu

# 测试配置加载
python -c "from jackclaw_team.main import load_config; import json; print(json.dumps(load_config(Path('config.yaml')), indent=2))"
```

## 📊 性能优化

### 1. 减少内存使用
- 减少 `session.max_history_turns` 数值
- 降低 `agent.max_iter` 迭代次数
- 使用更轻量的模型

### 2. 提高响应速度
- 使用更快的模型（如 qwen-turbo）
- 启用缓存机制
- 优化技能加载顺序

### 3. 监控指标
```bash
# 查看 Prometheus metrics
curl http://localhost:9100/metrics

# 使用 prometheus-cli 工具
pip install prometheus-client
prometheus-cli --url http://localhost:9100/metrics query 'jackclaw_inbound_messages_total'
```

## 🚨 常见错误码

| 错误信息 | 原因 | 解决方案 |
|---------|------|----------|
| `feishu.app_id / feishu.app_secret 不能为空` | 环境变量未设置 | 检查 `.env` 文件 |
| `This event loop is already running` | WebSocket 初始化冲突 | 检查 lark-oapi 导入时机 |
| `AllocationQuota.FreeTierOnly` | 免费额度用尽 | 关闭"仅免费模式" |
| `sbox: connection refused` | sandbox 服务未启动 | 启动 sandbox 容器 |
| `postgresql: connection refused` | pgvector 服务未启动 | 启动 pgvector 容器 |

## 📝 开发环境建议

### 1. 使用虚拟环境
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. 配置 IDE
- 设置 Python 解释器为 `.venv/bin/python`
- 配置环境变量从 `.env` 文件加载
- 启用类型检查（mypy）

### 3. 测试配置
```bash
# 运行单元测试
pytest tests/

# 运行集成测试
pytest tests/integration/

# 查看测试覆盖率
pytest --cov=jackclaw --cov=jackclaw_team
```

## 🔗 相关资源

- [飞书开放平台文档](https://open.feishu.cn/)
- [阿里云百炼文档](https://bailian.console.aliyun.com/)
- [CrewAI 文档](https://docs.crewai.com/)
- [pgvector 文档](https://github.com/pgvector/pgvector)