#!/usr/bin/env python3
"""
飞书发送消息测试 - 简化版
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
    print("❌ 错误：请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
    sys.exit(1)

from lark_oapi.client import Client as LarkClient
from lark_oapi.api.im.v1 import CreateMessageRequestBody, CreateMessageRequest, ListChatRequest

# 创建客户端
client = LarkClient.builder() \
    .app_id(app_id) \
    .app_secret(app_secret) \
    .build()

# 尝试列出最近的聊天
chat_resp = client.im.v1.chat.list(ListChatRequest.builder().build())

if chat_resp.success():
    chats = chat_resp.data.items
    print(f"找到 {len(chats)} 个聊天:")
    for chat in chats[:10]:
        print(f"  - {chat.name}")
        print(f"    chat_id: {chat.chat_id}")
    
    if chats:
        # 给第一个群聊发送测试消息
        target_chat = chats[0]
        print(f"\n发送测试消息到: {target_chat.name}")
        
        msg_resp = client.im.v1.message.create(
            CreateMessageRequest.builder()
            .receive_id(target_chat.chat_id)
            .msg_type("text")
            .content('{"text": "Hello from jack-claw! 测试消息"}')
            .build()
        )
        
        if msg_resp.success():
            print(f"✅ 消息发送成功!")
            print(f"   消息ID: {msg_resp.data.message_id}")
        else:
            print(f"❌ 消息发送失败: {msg_resp.msg}")
            print(f"   错误码: {msg_resp.code}")
else:
    print(f"获取聊天列表失败: {chat_resp.msg}")
    print(f"错误码: {chat_resp.code}")