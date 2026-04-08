# Phase 4: 沙盒集成

## 目标

实现本地代码执行环境，支持 Python/Bash 脚本执行。

## 交付物

| 文件 | 状态 | 说明 |
|------|------|------|
| `jackclaw/sandbox/client.py` | ✅ | 沙盒客户端 |
| `jackclaw/cleanup/service.py` | ✅ | 清理服务 |

## 关键特性

- **Python 执行**：写入临时文件后执行，自动清理
- **Bash 执行**：支持任意 shell 命令
- **超时控制**：可配置执行超时
- **自动清理**：每日 3:00 清理过期临时文件

## 配置

```yaml
sandbox:
  timeout_s: 60

data_dir: "./data"
```

## 验证方式

```bash
git checkout feature/phase-4-sandbox
pytest tests/ -v
python -m jackclaw.main
```

## 当前状态

**已完成** ✓

- SandboxClient 本地执行模式
- CleanupService 定时清理
- 工作目录隔离
