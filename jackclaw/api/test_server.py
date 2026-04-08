"""
TestAPI — 本地调试接口

提供 HTTP 接口用于本地测试，无需实际连接飞书。

接口：
- POST /api/test/message: 模拟发送消息
- DELETE /api/test/sessions: 清空所有会话

使用方式：
    curl -X POST http://127.0.0.1:9090/api/test/message \
        -H "Content-Type: application/json" \
        -d '{"routing_key": "p2p:test_user", "content": "Hello"}'

启动方式：
    在 config.yaml 中配置：
    debug:
      enable_test_api: true
      test_api_port: 9090
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from aiohttp import web

from jackclaw.models import InboundMessage

if TYPE_CHECKING:
    from jackclaw.runner import Runner
    from jackclaw.session.manager import SessionManager

logger = logging.getLogger(__name__)


def create_test_app(runner: "Runner", session_mgr: "SessionManager") -> web.Application:
    """
    创建 TestAPI 应用
    
    Args:
        runner: Runner 实例
        session_mgr: SessionManager 实例
        
    Returns:
        aiohttp Application
    """
    app = web.Application()
    app["runner"] = runner
    app["session_mgr"] = session_mgr

    # 注册路由
    app.router.add_post("/api/test/message", handle_test_message)
    app.router.add_delete("/api/test/sessions", handle_clear_sessions)

    return app


async def handle_test_message(request: web.Request) -> web.Response:
    """
    处理测试消息
    
    接收 JSON 格式的消息，构造 InboundMessage 并分发到 Runner。
    
    请求格式：
        {
            "routing_key": "p2p:test_user",
            "content": "Hello"
        }
    
    Args:
        request: HTTP 请求
        
    Returns:
        HTTP 响应
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"error": "Invalid JSON"},
            status=400,
        )

    routing_key = data.get("routing_key", "")
    content = data.get("content", "")

    if not routing_key or not content:
        return web.json_response(
            {"error": "routing_key and content required"},
            status=400,
        )

    # 构造 InboundMessage
    inbound = InboundMessage(
        routing_key=routing_key,
        content=content,
        msg_id=f"test_{int(time.time() * 1000)}",
        root_id="",
        sender_id="test_user",
        ts=int(time.time() * 1000),
    )

    # 分发到 Runner
    runner: "Runner" = request.app["runner"]
    await runner.dispatch(inbound)

    logger.info("Test message dispatched: %s -> %s", routing_key, content[:50])

    return web.json_response({
        "status": "dispatched",
        "msg_id": inbound.msg_id,
    })


async def handle_clear_sessions(request: web.Request) -> web.Response:
    """
    清空所有会话
    
    警告：此操作不可恢复！
    
    Args:
        request: HTTP 请求
        
    Returns:
        HTTP 响应
    """
    # TODO: 实现会话清理
    logger.warning("Clear sessions requested (not implemented)")
    return web.json_response({"status": "ok", "note": "Not implemented"})
