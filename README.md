# Phase 1: 核心消息处理

> JackClaw MVP 重写 - 第 2 阶段

## 📋 概述

本阶段实现消息处理核心流程，包含：
- 飞书 WebSocket 接入
- per-routing_key 串行队列
- Session 管理
- Slash 命令支持
- TestAPI 调试接口

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│                      飞书平台                              │
│                  (WebSocket 连接)                         │
└─────────────────────┬───────────────────────────────────┘
                      │ 事件推送
                      ▼
┌─────────────────────────────────────────────────────────┐
│                  FeishuListener                         │
│  - 解析 WebSocket 事件                                  │
│  - 转换为 InboundMessage                                │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                      Runner                              │
│  - per-routing_key 串行队列                            │
│  - Slash 命令拦截                                       │
│  - Agent 调度                                          │
└──────────┬─────────────────────────────┬───────────────┘
           │                             │
           ▼                             ▼
┌──────────────────┐          ┌──────────────────────┐
│   SessionManager │          │    FeishuSender      │
│  - 会话管理       │          │   - 消息发送         │
│  - 历史存储       │          │   - API 选择         │
└──────────────────┘          └──────────────────────┘
```

## 📁 文件结构

```
jack-claw/
├── jackclaw/
│   ├── main.py              # 进程入口
│   ├── config.py            # 配置加载
│   ├── models.py            # 数据模型
│   │
│   ├── feishu/             # 飞书接入层 ⭐
│   │   ├── listener.py      # WebSocket 监听
│   │   ├── sender.py        # 消息发送
│   │   └── session_key.py   # routing_key 解析
│   │
│   ├── session/             # 会话管理层 ⭐
│   │   ├── manager.py       # Session 管理器
│   │   └── models.py        # Session 数据模型
│   │
│   ├── runner.py            # 执行引擎 ⭐
│   │
│   └── api/                 # 调试接口 ⭐
│       └── test_server.py   # TestAPI
│
└── tests/
    ├── test_routing_key.py  # routing_key 测试
    └── test_session.py      # Session 测试
```

## 🔑 核心组件

### 1. FeishuListener (飞书监听器)

```python
"""
飞书 WebSocket 监听

职责：
- 维护 WebSocket 长连接
- 解析飞书事件为 InboundMessage
- 支持群消息白名单过滤
"""

class FeishuListener:
    async def start(self) -> None:
        """启动 WebSocket 连接"""
        
    def _handle_event(self, event: Event) -> None:
        """处理飞书事件"""
        
    def _handle_message_event(self, event: Event) -> None:
        """处理消息事件 → 转换为 InboundMessage"""
        
    def _parse_content(self, message) -> str:
        """解析消息内容（支持 text/post）"""
        
    def _parse_attachment(self, message) -> Attachment | None:
        """解析附件信息"""
```

### 2. Runner (执行引擎)

```python
"""
执行引擎

核心职责：
- per-routing_key 串行队列
- Slash Command 拦截
- Agent 调度
"""

class Runner:
    def __init__(self, session_mgr, sender, agent_fn=None, idle_timeout=300.0):
        """
        Args:
            session_mgr: Session 管理器
            sender: 消息发送器
            agent_fn: Agent 函数
            idle_timeout: worker 空闲超时（秒）
        """
        
    async def dispatch(self, inbound: InboundMessage) -> None:
        """消息入队，确保同一会话串行执行"""
        
    async def _worker(self, key: str) -> None:
        """per-routing_key worker"""
        # 1. 从队列获取消息
        # 2. 处理消息
        # 3. 空闲超时退出
        
    async def _handle(self, inbound: InboundMessage) -> None:
        """处理单条消息"""
        # 1. Slash 拦截
        # 2. Session 获取/创建
        # 3. Agent 执行
        # 4. 历史写入
        # 5. 发送回复
        
    async def _handle_slash(self, inbound: InboundMessage) -> str | None:
        """处理 slash 命令"""
```

### 3. SessionManager (会话管理)

```python
"""
Session 管理器

职责：
- routing_key → session_id 映射
- session 数据持久化
- 对话历史管理
"""

class SessionManager:
    async def get_or_create(self, routing_key: str) -> Session:
        """获取或创建 session"""
        
    async def create_new_session(self, routing_key: str) -> Session:
        """创建新 session"""
        
    async def load_history(self, session_id: str, limit: int = 20) -> list[MessageEntry]:
        """加载对话历史（最近 N 轮）"""
        
    async def append(self, session_id: str, user: str, assistant: str) -> None:
        """追加一轮对话"""
```

### 4. FeishuSender (消息发送)

```python
"""
飞书消息发送

支持：
- 单聊：CreateMessage API
- 群聊：CreateMessage API
- 话题：ReplyMessage API
"""

class FeishuSender:
    async def send(self, routing_key: str, content: str, root_id: str = "") -> None:
        """发送消息（自动选择 API）"""
        
    async def _create_message(self, routing: RoutingKey, content: str) -> None:
        """CreateMessage API（p2p/group）"""
        
    async def _reply_in_thread(self, root_id: str, content: str) -> None:
        """ReplyMessage API（thread）"""
```

### 5. TestAPI (调试接口)

```python
"""
TestAPI — 本地调试接口

无需真实飞书环境，直接发送消息测试
"""

# 接口
POST /api/test/message    # 发送测试消息
DELETE /api/test/sessions # 清空会话

# 使用
curl -X POST http://127.0.0.1:9090/api/test/message \
  -H "Content-Type: application/json" \
  -d '{"routing_key": "p2p:ou_test", "content": "你好"}'
```

## 🔀 routing_key 设计

| 类型 | 格式 | 示例 |
|------|------|------|
| 单聊 | `p2p:ou_xxx` | `p2p:ou_abc123` |
| 群聊 | `group:oc_xxx` | `group:oc_xyz789` |
| 话题 | `thread:oc_xxx:ot_xxx` | `thread:oc_chat:ot_thread` |

```python
# 解析
routing = parse_routing_key("p2p:ou_abc123")
assert routing.type == RoutingType.P2P

# 构建
key = build_routing_key(RoutingType.GROUP, chat_id="oc_xyz")
assert key == "group:oc_xyz"
```

## ⚡ Slash 命令

| 命令 | 功能 | 实现 |
|------|------|------|
| `/new` | 创建新对话 | `create_new_session()` |
| `/verbose on/off` | 开启/关闭详细模式 | `update_verbose()` |
| `/status` | 查看对话信息 | 查询 session |
| `/help` | 显示帮助 | 返回固定文本 |

**处理时机**: Runner 层，进入 Agent 之前拦截

## 📊 设计决策

### D-01: per-routing_key 队列

**问题**: 如何确保消息顺序？

**方案**: 每个 routing_key 一个队列 + worker

```
优点：
- 同一会话串行，避免竞态
- 不同会话并行，提高吞吐
- worker 空闲退出，节省资源
```

### D-02: Session 持久化

**问题**: 如何存储对话历史？

**方案**: JSON 文件，每个 session 一个文件

```
data/sessions/
├── index.json              # routing → session 映射
└── s-abc123.json          # session 数据
```

## 🚀 运行

```bash
# 启动
python -m jackclaw.main

# TestAPI 测试
curl -X POST http://127.0.0.1:9090/api/test/message \
  -d '{"routing_key": "p2p:ou_test", "content": "/help"}'
```

## ➡️ 下一步

[Phase 2: Agent 集成](../feature/phase-2-agent)
