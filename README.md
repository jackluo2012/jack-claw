# Phase 4: 沙盒集成

> JackClaw MVP 重写 - 第 5 阶段

## 📋 概述

本阶段实现沙盒执行和文件清理：
- 本地 Python/Bash 执行
- 文件清理服务
- 每日定时清理

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│                    MainAgent                             │
│  - 构建系统提示                                         │
│  - 调用 LLM                                            │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                 SandboxClient                             │
│  - execute_python()                                    │
│  - execute_bash()                                      │
│  - read_file() / write_file()                          │
└─────────────────────────────────────────────────────────┘
```

## 📁 新增文件

```
jack-claw/
├── jackclaw/
│   ├── sandbox/                   # 沙盒层 ⭐
│   │   └── client.py            # 沙盒客户端
│   │
│   └── cleanup/                  # 清理层 ⭐
│       └── service.py           # 清理服务
```

## 🔑 核心组件

### 1. SandboxClient (沙盒客户端)

```python
"""
沙盒客户端

职责：
- 执行 Python 脚本
- 执行 Bash 命令
- 文件读写
"""

class SandboxClient:
    def __init__(self, workspace_dir: Path, timeout: float = 60.0):
        """
        Args:
            workspace_dir: 工作目录
            timeout: 执行超时（秒）
        """
        
    async def execute_python(self, script: str, cwd: Path | None = None) -> dict:
        """
        执行 Python 脚本
        
        Args:
            script: Python 代码
            cwd: 工作目录
        
        Returns:
            {
                "success": bool,
                "returncode": int,
                "stdout": str,
                "stderr": str,
            }
        """
        # 1. 写入临时脚本
        # 2. 执行 python3
        # 3. 返回结果
        
    async def execute_bash(self, command: str, cwd: Path | None = None) -> dict:
        """
        执行 Bash 命令
        
        Args:
            command: 命令
            cwd: 工作目录
        
        Returns:
            {
                "success": bool,
                "returncode": int,
                "stdout": str,
                "stderr": str,
            }
        """
        
    async def read_file(self, path: Path) -> str:
        """读取文件"""
        
    async def write_file(self, path: Path, content: str) -> bool:
        """写入文件"""
```

### 2. CleanupService (清理服务)

```python
"""
文件清理服务

职责：
- 清理过期文件
- 定时执行
"""

class CleanupService:
    def __init__(
        self,
        data_dir: Path,
        uploads_max_days: int = 7,
        outputs_max_days: int = 30,
    ):
        """
        Args:
            data_dir: 数据目录
            uploads_max_days: 上传文件保留天数
            outputs_max_days: 输出文件保留天数
        """
        
    async def sweep(self) -> None:
        """执行清理"""
        # 1. 遍历 sessions
        # 2. 清理 uploads/
        # 3. 清理 outputs/
```

## 📁 目录结构

```
data/
├── workspace/
│   ├── .config/                # 配置
│   │   ├── feishu.json        # 飞书凭证
│   │   └── baidu.json         # 百度凭证
│   │
│   └── sessions/
│       ├── s-abc123/
│       │   ├── uploads/       # 用户上传（7 天）
│       │   ├── outputs/       # Skill 产出（30 天）
│       │   └── tmp/           # 临时文件
│       │
│       └── s-def456/
│
├── sessions/
│   ├── index.json             # routing_key → session 映射
│   ├── s-abc123.json         # session 数据
│   └── s-def456.json
│
├── traces/                    # 执行追踪（30 天）
│
└── logs/                      # 日志文件
```

## 🧹 清理策略

| 目录 | 保留时间 | 说明 |
|------|----------|------|
| uploads/ | 7 天 | 用户上传文件 |
| outputs/ | 30 天 | Skill 产出文件 |
| tmp/ | 1 天 | 临时文件 |
| traces/ | 30 天 | 执行追踪 |
| sessions/*.jsonl | 365 天 | 对话历史 |

**触发时机**：
- 启动时执行一次
- 每日 3:00 定时执行

## 📊 设计决策

### D-01: 沙盒实现

**问题**: 如何隔离执行？

**MVP 方案**: 本地执行

```
优点：
- 简单，无依赖
- 易于调试

改进：
- 接入 AIO-Sandbox (Docker)
- 更强的隔离
```

### D-02: 清理策略

**问题**: 如何清理过期文件？

**方案**: 基于 mtime 删除

```
优点：
- 简单
- 可配置
```

## 🚀 使用

```python
# 使用 Sandbox
sandbox = SandboxClient(workspace_dir=Path("./data/workspace"))
result = await sandbox.execute_python("print('hello')")
print(result["stdout"])  # "hello\n"

# 使用 Cleanup
cleanup = CleanupService(data_dir=Path("./data"))
await cleanup.sweep()
```

## ➡️ 下一步

[Phase 5: 定时任务](../feature/phase-5-cron)
