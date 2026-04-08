# Phase 1: 核心消息处理

## 目标

实现飞书消息接收、会话管理、消息路由。

## 交付物

| 文件 | 状态 | 说明 |
|------|------|------|
| `jackclaw/feishu/listener.py` | ✅ | WebSocket 消息监听器 |
| `jackclaw/feishu/sender.py` | ✅ | 消息发送器 |
| `jackclaw/feishu/session_key.py` | ✅ | routing_key 解析 |
| `jackclaw/runner.py` | ✅ | 消息分发引擎（per-routing_key 队列） |
| `jackclaw/session/manager.py` | ✅ | 会话管理器 |
| `jackclaw/session/models.py` | ✅ | 会话数据模型 |
| `jackclaw/api/test_server.py` | ✅ | 本地调试 HTTP 接口 |
| `tests/test_routing_key.py` | ✅ | routing_key 测试 |
| `tests/test_session.py` | ✅ | 会话测试 |

## 关键特性

- **routing_key 路由**：`p2p:ou_xxx` / `group:oc_xxx` / `thread:oc_xxx:ot_xxx`
- **串行处理**：每个 routing_key 独立队列，保证消息顺序
- **Slash Commands**：`/new` `/verbose` `/help` `/status`
- **TestAPI**：本地调试接口 `POST /api/test/message`

## 验证方式

```bash
git checkout feature/phase-1-messaging
pytest tests/ -v
python -m jackclaw.main  # 需要配置 .env
```

## 当前状态

**已完成** ✓

- 飞书 WebSocket 连接（已适配 lark_oapi v1.5.3）
- 消息发送（文本、卡片）
- 会话持久化（JSON 文件）
- 9 个测试全部通过
