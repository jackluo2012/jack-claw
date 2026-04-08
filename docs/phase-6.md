# Phase 6: 可观测性

## 目标

实现日志、指标、监控接口。

## 交付物

| 文件 | 状态 | 说明 |
|------|------|------|
| `jackclaw/observability/logging_config.py` | ✅ | 日志配置 |
| `jackclaw/observability/metrics.py` | ✅ | Prometheus 指标 |
| `jackclaw/observability/metrics_server.py` | ✅ | 指标 HTTP 服务 |

## Prometheus 指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `jackclaw_feishu_messages_total` | Counter | 飞书消息总数 |
| `jackclaw_runner_workers_active` | Gauge | 活跃 worker 数 |
| `jackclaw_runner_queue_size` | Gauge | 队列大小 |
| `jackclaw_agent_requests_total` | Counter | Agent 请求总数 |
| `jackclaw_agent_errors_total` | Counter | Agent 错误总数 |

## 配置

```yaml
observability:
  metrics_port: 9091
  log_level: "INFO"
```

## 验证方式

```bash
git checkout feature/phase-6-observability  # 仅远程分支
pytest tests/ -v
python -m jackclaw.main

# 访问指标
curl http://localhost:9091/metrics
```

## 当前状态

**已完成** ✓

- Metrics 模块实现
- 指标定义
- Prometheus 格式导出

## 待完善

- [ ] Runner 集成 metrics 调用
- [ ] metrics_server 启动逻辑
- [ ] logging_config 应用
