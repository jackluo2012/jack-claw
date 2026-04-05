"""
Prometheus 指标 HTTP 服务
"""

from __future__ import annotations

import logging
from aiohttp import web

from jackclaw.observability.metrics import metrics

logger = logging.getLogger(__name__)


async def handle_metrics(request: web.Request) -> web.Response:
    """处理 /metrics 请求"""
    output = metrics.to_prometheus()
    return web.Response(text=output, content_type="text/plain; version=0.0.4")


async def start_metrics_server(host: str = "127.0.0.1", port: int = 9100) -> None:
    """启动指标服务"""
    app = web.Application()
    app.router.add_get("/metrics", handle_metrics)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    logger.info("Metrics server started: http://%s:%d/metrics", host, port)
    try:
        import asyncio
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
