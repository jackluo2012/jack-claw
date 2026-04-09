#!/usr/bin/env python3
"""测试处理器注册是否正确"""

from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1

def test_handler(event: P2ImMessageReceiveV1) -> None:
    print(f"[TEST HANDLER] Called with event: {event}")

# 构建处理器
builder = EventDispatcherHandler.builder("", "")
handler = builder.register_p2_im_message_receive_v1(test_handler).build()

# 检查 processor map
print("Registered processors in _processorMap:")
for key in sorted(handler._processorMap.keys()):
    print(f"  {key}")

# 检查是否包含消息接收事件
msg_key = "p2.im.message.receive_v1"
if msg_key in handler._processorMap:
    print(f"\n✓ Found processor for {msg_key}")
    processor = handler._processorMap[msg_key]
    print(f"  Processor type: {type(processor)}")
else:
    print(f"\n✗ Processor NOT found for {msg_key}")

# 模拟一个消息事件 payload
test_payload = b'''{
    "schema": "2.0",
    "header": {
        "event_id": "test-event-id",
        "event_type": "im.message.receive_v1",
        "create_time": "1234567890000"
    },
    "event": {
        "message": {
            "message_id": "test-msg-id",
            "root_id": "",
            "parent_id": "",
            "create_time": "1234567890000",
            "chat_id": "test-chat-id",
            "chat_type": "p2p",
            "message_type": "text",
            "content": "{\\"text\\": \\"hello\\"}"
        },
        "sender": {
            "sender_id": {
                "open_id": "test-sender-id"
            }
        }
    }
}'''

print("\n\nTesting do_without_validation with sample payload...")
try:
    result = handler.do_without_validation(test_payload)
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
