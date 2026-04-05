# Phase 6: 可观测性

> JackClaw MVP 重写 - 第 7 阶段

## 📋 概述

本阶段实现完整可观测性：
- 日志配置（控制台 + JSON 文件）
- Prometheus 指标
- /metrics HTTP 端点

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│                     应用代码                               │
│  logging.info() / metrics.counter().inc()               │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              observability/                               │
│  - logging_config.py                                   │
│  - metrics.py                                          │
│  - metrics_server.py                                   │
└─────────────────────────────────────────────────────────┘
          │
          ├──────────────────┐
          ▼                  ▼
    ┌──────────┐    ┌──────────────┐
    │ 控制台    │    │ metrics_server│
    │ 可读格式  │    │ /metrics    │
    └──────────┘    └──────────────┘
```

## 📁 新增文件

```
jack-claw/
├── jackclaw/
│   └── observability/                # 可观测层 ⭐
│       ├── logging_config.py       # 日志配置
│       ├── metrics.py             # Prometheus 指标
│       └── metrics_server.py      # 指标服务
```

## 🔑 核心组件

### 1. 日志配置 (logging_config.py)

```python
"""
日志配置

双输出：
- 控制台：可读格式
- 文件：JSON 结构化
"""

class JsonFormatter(logging.Formatter):
    """JSON 格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        })

def setup_logging(log_dir: Path | None = None) -> None:
    """初始化日志"""
    # 控制台: 可读格式
    # 文件: JSON 格式
```

**输出示例**：

```bash
# 控制台
2026-04-06 08:00:00 [INFO] jackclaw.main: JackClaw starting...

# 文件
{"ts":"2026-04-06T08:00:00Z","level":"INFO","logger":"jackclaw.main","msg":"JackClaw starting..."}
```

### 2. Prometheus 指标 (metrics.py)

```python
"""
Prometheus 指标

指标类型：
- Counter: 计数器
- Gauge: 仪表
"""

@dataclass
class Counter:
    """计数器（单调递增）"""
    name: str
    help_text: str = ""
    _value: float = 0.0
    
    def inc(self, amount: float = 1.0) -> None:
        self._value += amount

@dataclass
class Gauge:
    """仪表（可增可减）"""
    name: str
    help_text: str = ""
    _value: float = 0.0
    
    def set(self, value: float) -> None:
        self._value = value
    
    def inc(self, amount: float = 1.0) -> None:
        self._value += amount
    
    def dec(self, amount: float = 1.0) -> None:
        self._value -= amount

class Metrics:
    """指标集合"""
    
    def counter(self, name: str, help_text: str = "") -> Counter:
        """获取或创建计数器"""
    
    def gauge(self, name: str, help_text: str = "") -> Gauge:
        """获取或创建仪表"""
    
    def to_prometheus(self) -> str:
        """导出 Prometheus 格式"""
```

### 3. 预定义指标

```python
# 全局实例
feishu_messages_total = metrics.counter(
    "jackclaw_feishu_messages_total",
    "Total Feishu messages"
)

runner_workers_active = metrics.gauge(
    "jackclaw_runner_workers_active",
    "Active runner workers"
)

runner_queue_size = metrics.gauge(
    "jackclaw_runner_queue_size",
    "Runner queue size"
)

agent_requests_total = metrics.counter(
    "jackclaw_agent_requests_total",
    "Total Agent requests"
)

agent_errors_total = metrics.counter(
    "jackclaw_agent_errors_total",
    "Total Agent errors"
)
```

### 4. 指标服务 (metrics_server.py)

```python
"""
Prometheus 指标 HTTP 服务

端点：GET /metrics
"""

async def handle_metrics(request: web.Request) -> web.Response:
    """处理 /metrics 请求"""
    output = metrics.to_prometheus()
    return web.Response(
        text=output,
        content_type="text/plain; version=0.0.4"
    )

async def start_metrics_server(host: str = "127.0.0.1", port: int = 9100) -> None:
    """启动指标服务"""
```

## 📊 指标列表

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `jackclaw_feishu_messages_total` | Counter | 飞书消息总数 |
| `jackclaw_runner_workers_active` | Gauge | 活跃 worker 数 |
| `jackclaw_runner_queue_size` | Gauge | 队列大小 |
| `jackclaw_agent_requests_total` | Counter | Agent 请求总数 |
| `jackclaw_agent_errors_total` | Counter | Agent 错误总数 |

## 📝 Prometheus 输出格式

```bash
curl http://127.0.0.1:9100/metrics
```

```
# HELP jackclaw_feishu_messages_total Total Feishu messages
# TYPE jackclaw_feishu_messages_total counter
jackclaw_feishu_messages_total 42

# HELP jackclaw_runner_workers_active Active runner workers
# TYPE jackclaw_runner_workers_active gauge
jackclaw_runner_workers_active 3

# HELP jackclaw_runner_queue_size Runner queue size
# TYPE jackclaw_runner_queue_size gauge
jackclaw_runner_queue_size 0

# HELP jackclaw_agent_requests_total Total Agent requests
# TYPE jackclaw_agent_requests_total counter
jackclaw_agent_requests_total 38

# HELP jackclaw_agent_errors_total Total Agent errors
# TYPE jackclaw_agent_errors_total counter
jackclaw_agent_errors_total 2
```

## 🚀 使用

```bash
# 启动
python -m jackclaw.main

# 查看日志
tail -f data/logs/jackclaw.log | jq

# 查看指标
curl http://127.0.0.1:9100/metrics

# Grafana 集成（可选）
# Prometheus 配置:
# scrape_configs:
#   - job_name: 'jackclaw'
#     static_configs:
#       - targets: ['localhost:9100']
```

## 📊 设计决策

### D-01: 日志格式

**方案**: 控制台可读 + 文件 JSON

```
优点：
- 控制台易读
- 文件易解析
- 支持结构化查询
```

### D-02: 指标实现

**方案**: 自实现简化版

```
优点：
- 无依赖
- 易于理解
- 满足基本需求

改进：
- 使用 prometheus_client
- 支持 labels
```

## ✅ 总结

JackClaw MVP 完成！

| Phase | 功能 |
|-------|------|
| Phase 0 | 项目骨架 |
| Phase 1 | 核心消息处理 |
| Phase 2 | Agent 集成 |
| Phase 3 | Skills 系统 |
| Phase 4 | 沙盒集成 |
| Phase 5 | 定时任务 |
| Phase 6 | 可观测性 |

**总代码量**: ~2,700 行
**总文件数**: 24 个
