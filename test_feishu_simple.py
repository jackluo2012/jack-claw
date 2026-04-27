#!/usr/bin/env python3
"""
飞书 WebSocket 简单测试脚本

用法：
1. 确保 .env 文件中有 FEISHU_APP_ID 和 FEISHU_APP_SECRET
2. 运行：python test_feishu_simple.py
3. 在飞书发送消息给机器人，看是否能收到
"""

import os
import sys
from pathlib import Path

# 加载 .env 文件
def load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value.strip().strip('"').strip("'")

load_env()

app_id = os.environ.get("FEISHU_APP_ID", "")
app_secret = os.environ.get("FEISHU_APP_SECRET", "")

if not app_id or not app_secret:
    print("错误：请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量")
    print(f"当前 app_id: {app_id[:10]}..." if app_id else "当前 app_id: 空")
    print(f"当前 app_secret: {app_secret[:10]}..." if app_secret else "当前 app_secret: 空")
    sys.exit(1)

print(f"使用 app_id: {app_id[:15]}...")
print(f"使用 app_secret: {app_secret[:10]}...")

# 导入飞书 SDK
from lark_oapi.ws import Client as WsClient
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1
from lark_oapi.core.enum import LogLevel

# 消息计数器
msg_count = 0

def on_message_received(event: P2ImMessageReceiveV1) -> None:
    """消息接收回调"""
    global msg_count
    msg_count += 1
    
    print(f"\n{'='*60}")
    print(f"[消息 #{msg_count}] 收到飞书消息事件！")
    print(f"{'='*60}")
    
    try: 
        msg = event.event.message
        sender = event.event.sender
        
        print(f"消息ID: {msg.message_id}")
        print(f"聊天ID: {msg.chat_id}")
        print(f"聊天类型: {msg.chat_type}")
        print(f"消息类型: {msg.message_type}")
        print(f"发送者: {sender.sender_id.open_id}")
        print(f"内容: {msg.content}")
        
        # 如果是文本消息，解析内容
        if msg.message_type == "text":
            import json
            try:
                content = json.loads(msg.content)
                text = content.get("text", "")
                print(f"文本内容: {text}")
            except:
                print(f"文本解析失败")
                
    except Exception as e:
        print(f"解析消息时出错: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"{'='*60}\n")

# 构建事件处理器
event_handler = (
    EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(on_message_received)
    .build()
)

# 创建 WebSocket 客户端
client = WsClient(
    app_id=app_id,
    app_secret=app_secret,
    event_handler=event_handler,
)

print("\n" + "="*60)
print("飞书 WebSocket 测试启动")
print("="*60)
print("请在飞书发送消息给机器人...")
print("按 Ctrl+C 停止\n")

try:
    # 启动客户端（阻塞）
    client.start()
except KeyboardInterrupt:
    print("\n\n用户中断，程序退出")
    print(f"总共收到 {msg_count} 条消息")
except Exception as e:
    print(f"\n发生错误: {e}")
    import traceback
    traceback.print_exc()
