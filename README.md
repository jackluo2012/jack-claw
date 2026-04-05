# Phase 5: 定时任务

> JackClaw MVP 重写 - 第 6 阶段

## 📋 概述

本阶段实现定时任务系统：
- 三种调度模式（at/every/cron）
- 任务持久化
- 自动执行

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│                   CronService                              │
│  - 任务调度                                              │
│  - 执行循环                                              │
│  - 状态管理                                             │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼ dispatch(InboundMessage)
┌─────────────────────────────────────────────────────────┐
│                      Runner                               │
│  - 消息入队                                              │
│  - 发送给用户                                            │
└─────────────────────────────────────────────────────────┘
```

## 📁 新增文件

```
jack-claw/
├── jackclaw/
│   └── cron/                     # 定时任务层 ⭐
│       ├── models.py           # 任务模型
│       └── service.py          # CronService
```

## 🔑 核心组件

### 1. 数据模型

```python
"""
定时任务数据模型
"""

class ScheduleKind(str, Enum):
    """调度类型"""
    AT = "at"        # 一次性
    EVERY = "every"  # 固定间隔
    CRON = "cron"    # Cron 表达式

@dataclass
class Schedule:
    """调度配置"""
    kind: ScheduleKind
    at: str = ""           # AT: ISO 时间戳
    every_ms: int = 0      # EVERY: 间隔毫秒
    anchor_ms: int = 0     # EVERY: 锚点
    expr: str = ""         # CRON: 表达式
    tz: str = "Asia/Shanghai"  # CRON: 时区

@dataclass
class CronJob:
    """定时任务"""
    id: str
    name: str
    schedule: Schedule
    routing_key: str       # 目标会话
    content: str           # 消息内容
    enabled: bool = True
    created_at: int = 0
    next_run_at_ms: int = 0
    last_run_at_ms: int = 0
```

### 2. CronService (定时任务服务)

```python
"""
定时任务服务

职责：
- 任务调度
- 执行循环
- 状态管理
"""

class CronService:
    async def start(self) -> None:
        """启动服务"""
        # 1. 加载任务
        # 2. 调度启用的任务
        
    async def stop(self) -> None:
        """停止服务"""
        
    def add_job(self, job: CronJob) -> None:
        """添加任务"""
        
    def remove_job(self, job_id: str) -> None:
        """移除任务"""
        
    def list_jobs(self) -> list[CronJob]:
        """列出任务"""
        
    async def _run_job_loop(self, job: CronJob) -> None:
        """任务执行循环"""
        while enabled:
            # 1. 计算延迟
            delay = _calc_delay(job)
            # 2. 等待
            await asyncio.sleep(delay / 1000)
            # 3. 执行
            await _execute_job(job)
            # 4. 更新状态
            if at:
                enabled = False  # 一次性任务禁用
```

## 📅 调度模式

### 1. AT（一次性）

```yaml
schedule:
  kind: "at"
  at: "2026-04-06T09:00:00+08:00"
```

```python
# 计算延迟
at_dt = datetime.fromisoformat(schedule.at)
at_ms = int(at_dt.timestamp() * 1000)
delay = at_ms - now_ms
```

**特点**：
- 执行后自动禁用
- 适合提醒、一次性任务

### 2. EVERY（固定间隔）

```yaml
schedule:
  kind: "every"
  every_ms: 86400000    # 24 小时
  anchor_ms: 1712345678000  # 可选锚点
```

```python
# 计算延迟
if first_run:
    elapsed = (now_ms - anchor_ms) % every_ms
    delay = every_ms - elapsed
else:
    delay = every_ms
```

**特点**：
- 持续执行
- 适合周期任务

### 3. CRON（Cron 表达式）

```yaml
schedule:
  kind: "cron"
  expr: "0 9 * * 1"       # 每周一 9:00
  tz: "Asia/Shanghai"
```

```python
from croniter import croniter

cron = croniter(schedule.expr, now)
next_dt = cron.get_next(datetime)
delay = next_dt.timestamp() * 1000 - now_ms
```

**特点**：
- 灵活配置
- 适合复杂调度

## 📁 任务存储

```json
// data/cron/tasks.json
{
  "jobs": [
    {
      "id": "remind-1",
      "name": "开会提醒",
      "schedule": {
        "kind": "at",
        "at": "2026-04-06T09:00:00+08:00"
      },
      "routing_key": "p2p:ou_abc123",
      "content": "10分钟后开会",
      "enabled": true,
      "created_at": 1712345678000,
      "next_run_at_ms": 1712403600000,
      "last_run_at_ms": 0
    }
  ]
}
```

## 🔄 执行流程

```
添加任务 → 调度循环 → 计算延迟 → 等待 → 执行 → 更新状态
                                      ↓
                            dispatch(InboundMessage)
                                      ↓
                              Runner → 发送给用户
```

## 📊 设计决策

### D-01: 调度实现

**方案**: asyncio + sleep

```
优点：
- 无依赖
- 精确
- 易于调试
```

### D-02: 任务执行

**方案**: 构造 InboundMessage，dispatch 到 Runner

```
优点：
- 复用 Runner 逻辑
- 统一处理流程
```

## 🚀 使用

```bash
# 手动添加任务（修改 data/cron/tasks.json）
{
  "jobs": [
    {
      "id": "test-1",
      "name": "测试任务",
      "schedule": {"kind": "at", "at": "2026-04-06T20:00:00+08:00"},
      "routing_key": "p2p:ou_test",
      "content": "定时任务测试",
      "enabled": true
    }
  ]
}

# 启动
python -m jackclaw.main
# 输出: CronService started, 1 jobs scheduled
# 输出: Executing cron job: test-1
```

## ➡️ 下一步

[Phase 6: 可观测性](../feature/phase-6-observability)
