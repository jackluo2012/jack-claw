# Phase 5: 定时任务

## 目标

实现定时任务调度，支持 at/every/cron 三种模式。

## 交付物

| 文件 | 状态 | 说明 |
|------|------|------|
| `jackclaw/cron/models.py` | ✅ | 定时任务数据模型 |
| `jackclaw/cron/service.py` | ✅ | 定时任务服务 |

## 三种调度模式

### 1. AT（一次性）

```json
{
  "kind": "at",
  "at": "2024-01-15T09:00:00Z"
}
```

### 2. EVERY（周期性）

```json
{
  "kind": "every",
  "every_ms": 3600000,
  "anchor_ms": 1704067200000
}
```

### 3. CRON（Cron 表达式）

```json
{
  "kind": "cron",
  "expr": "0 9 * * 1-5",
  "tz": "Asia/Shanghai"
}
```

## 关键特性

- **持久化**：任务保存到 `data/cron/tasks.json`
- **自动恢复**：服务启动时恢复已调度任务
- **消息注入**：到时任务作为 InboundMessage 注入 Runner

## 验证方式

```bash
git checkout feature/phase-5-cron  # 仅远程分支
pytest tests/ -v
python -m jackclaw.main
```

## 当前状态

**已完成** ✓

- CronJob 数据模型
- CronService 调度服务
- 三种调度模式支持
- 任务持久化和恢复

## 依赖

需要安装 `croniter` 包：
```bash
pip install croniter
```
