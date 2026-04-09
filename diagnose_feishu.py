#!/usr/bin/env python3
"""
飞书配置诊断脚本

检查应用配置和权限
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
    print("❌ 错误：请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量")
    sys.exit(1)

print(f"App ID: {app_id}")
print(f"App Secret: {app_secret[:10]}...")
print()

# 测试获取 tenant_access_token
import requests

print("=" * 60)
print("1. 测试获取 tenant_access_token")
print("=" * 60)

url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
data = resp.json()

if data.get("code") == 0:
    token = data.get("tenant_access_token", "")[:20] + "..."
    expire = data.get("expire", 0)
    print(f"✅ 获取 token 成功: {token}")
    print(f"   有效期: {expire} 秒")
else:
    print(f"❌ 获取 token 失败: {data}")
    sys.exit(1)

token = data.get("tenant_access_token")

# 测试获取机器人信息
print()
print("=" * 60)
print("2. 测试获取机器人信息")
print("=" * 60)

url = "https://open.feishu.cn/open-apis/bot/v3/info"
resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
data = resp.json()

if data.get("code") == 0:
    bot = data.get("bot", {})
    print(f"✅ 获取机器人信息成功")
    print(f"   机器人名称: {bot.get('app_name', 'N/A')}")
    print(f"   机器人 ID: {bot.get('open_id', 'N/A')[:20]}...")
    print(f"   激活状态: {bot.get('is_activate', False)}")
else:
    print(f"❌ 获取机器人信息失败: {data}")

# 测试获取应用信息
print()
print("=" * 60)
print("3. 检查应用权限")
print("=" * 60)

url = "https://open.feishu.cn/open-apis/application/v6/applications"
resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
data = resp.json()

if data.get("code") == 0:
    apps = data.get("data", {}).get("apps", [])
    for app in apps:
        if app.get("app_id") == app_id:
            print(f"✅ 找到应用: {app.get('app_name', 'N/A')}")
            print(f"   应用状态: {app.get('state', 'N/A')}")
            print(f"   可见范围: {app.get('visibility', 'N/A')}")
            break
else:
    print(f"⚠️ 获取应用列表失败: {data.get('msg', 'Unknown error')}")

# 检查事件订阅配置
print()
print("=" * 60)
print("4. 手动检查清单（请在飞书开放平台确认）")
print("=" * 60)
print("""
请访问: https://open.feishu.cn/app/{app_id}/event/subscribe

检查以下配置：

□ 1. 事件订阅方式
   - 确认是 "WebSocket" 模式（不是 HTTP 回调模式）

□ 2. 已添加的事件
   - im.message.receive_v1 (接收消息)
   - im.chat.member.bot.added_v1 (机器人入群)

□ 3. 应用发布状态
   - 应用管理 → 版本管理与发布
   - 确认有已发布的版本
   - 状态应为 "已发布"

□ 4. 机器人启用状态
   - 应用功能 → 机器人
   - 确认机器人已启用

□ 5. 权限配置
   - 权限管理 → 权限配置
   - 确认有以下权限：
     * im:chat:readonly
     * im:message:send
     * im:message:readonly (如果存在)

□ 6. 机器人已添加到聊天
   - 在飞书中，进入群设置 → 群机器人 → 添加机器人
   - 或直接与机器人私聊
""")

print()
print("=" * 60)
print("诊断完成")
print("=" * 60)
