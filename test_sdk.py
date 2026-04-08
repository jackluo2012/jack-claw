#!/usr/bin/env python3
"""测试 lark_oapi SDK 版本"""
import sys
sys.path.insert(0, "/home/jackluo/my/jack-claw/.venv/lib/python3.12/site-packages")

from lark_oapi.ws import Client as WsClient
print("WsClient methods:", [m for m in dir(WsClient) if not m.startswith("_")])

try:
    from lark_oapi.ws import Event
    print("Event import: OK")
except ImportError as e:
    print(f"Event import failed: {e}")