"""
端到端测试 - 模拟飞书消息流

测试场景：
1. 用户发送消息 -> Runner.dispatch()
2. Runner 解析 slash command -> 处理 /help
3. Runner 调用 Agent -> 返回响应
4. Sender 发送响应
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from jackclaw.models import InboundMessage
from jackclaw.session.manager import SessionManager
from jackclaw.runner import Runner


async def mock_agent_fn(
    user_message: str,
    history: list,
    session_id: str = "",
    routing_key: str = "",
    root_id: str = "",
    verbose: bool = False,
) -> str:
    """Mock Agent 返回固定响应"""
    return f"Echo: {user_message}"


class MockSender:
    def __init__(self):
        self.sent_messages = []

    async def send(self, routing_key: str, content: str, root_id: str = "") -> None:
        self.sent_messages.append({"routing_key": routing_key, "content": content, "root_id": root_id})

    async def send_text(self, routing_key: str, content: str, root_id: str = "") -> None:
        await self.send(routing_key, content, root_id)


async def test_e2e_message_flow():
    """端到端消息流测试"""
    # Setup
    data_dir = Path("/tmp/jackclaw_test_e2e")
    data_dir.mkdir(exist_ok=True)
    
    session_mgr = SessionManager(data_dir=data_dir)
    sender = MockSender()
    runner = Runner(
        session_mgr=session_mgr,
        sender=sender,
        agent_fn=mock_agent_fn,
        idle_timeout=60.0,
    )

    # Test 1: Slash command /help
    msg_help = InboundMessage(
        routing_key="p2p:ou_test123",
        content="/help",
        msg_id="msg_001",
        root_id="",
        sender_id="ou_test",
        ts=1234567890000,
    )
    await runner.dispatch(msg_help)
    await asyncio.sleep(0.1)  # 等待处理

    assert len(sender.sent_messages) == 1
    assert "可用命令" in sender.sent_messages[0]["content"]
    print("✅ /help 命令正常")

    # Test 2: 普通消息 -> Agent
    sender.sent_messages.clear()
    msg_echo = InboundMessage(
        routing_key="p2p:ou_test123",
        content="你好",
        msg_id="msg_002",
        root_id="",
        sender_id="ou_test",
        ts=1234567891000,
    )
    await runner.dispatch(msg_echo)
    await asyncio.sleep(0.1)

    assert len(sender.sent_messages) == 1
    assert sender.sent_messages[0]["content"] == "Echo: 你好"
    print("✅ 普通消息正常")

    # Test 3: /new 创建新会话
    sender.sent_messages.clear()
    msg_new = InboundMessage(
        routing_key="p2p:ou_test123",
        content="/new",
        msg_id="msg_003",
        root_id="",
        sender_id="ou_test",
        ts=1234567892000,
    )
    await runner.dispatch(msg_new)
    await asyncio.sleep(0.1)

    assert len(sender.sent_messages) == 1
    assert "已创建新对话" in sender.sent_messages[0]["content"]
    print("✅ /new 正常")

    # Test 4: /verbose on
    sender.sent_messages.clear()
    msg_verbose = InboundMessage(
        routing_key="p2p:ou_test123",
        content="/verbose on",
        msg_id="msg_004",
        root_id="",
        sender_id="ou_test",
        ts=1234567893000,
    )
    await runner.dispatch(msg_verbose)
    await asyncio.sleep(0.1)

    assert "详细模式已开启" in sender.sent_messages[0]["content"]
    print("✅ /verbose on 正常")

    # Cleanup
    await runner.shutdown()
    # 删除测试数据
    import shutil
    if data_dir.exists():
        shutil.rmtree(data_dir)

    print("\n🎉 所有端到端测试通过!")


if __name__ == "__main__":
    asyncio.run(test_e2e_message_flow())