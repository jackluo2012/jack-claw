"""
TestAPI — 本地调试接口
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
    """创建 TestAPI 应用"""
    app = web.Application()
    app["runner"] = runner
    app["session_mgr"] = session_mgr
    app.router.add_post("/api/test/message", handle_test_message)
    app.router.add_delete("/api/test/sessions", handle_clear_sessions)
    return app


async def handle_test_message(request: web.Request) -> web.Response:
    """处理测试消息"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    routing_key = data.get("routing_key", "")
    content = data.get("content", "")
    if not routing_key or not content:
        return web.json_response({"error": "routing_key and content required"}, status=400)

    inbound = InboundMessage(
        routing_key=routing_key,
        content=content,
        msg_id=f"test_{int(time.time() * 1000)}",
        root_id="",
        sender_id="test_user",
        ts=int(time.time() * 1000),
    )

    runner: "Runner" = request.app["runner"]
    await runner.dispatch(inbound)

    return web.json_response({"status": "dispatched", "msg_id": inbound.msg_id})


async def handle_clear_sessions(request: web.Request) -> web.Response:
    """清空所有 session"""
    return web.json_response({"status": "ok"})
