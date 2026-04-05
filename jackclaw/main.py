"""
JackClaw 进程入口 - Phase 1

包含：
- SessionManager
- Runner
- FeishuListener
- TestAPI
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from lark_oapi.client import Client, LogLevel

from jackclaw.config import load_config, get_feishu_credentials
from jackclaw.session.manager import SessionManager
from jackclaw.runner import Runner
from jackclaw.feishu.listener import FeishuListener, run_forever
from jackclaw.feishu.sender import FeishuSender

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def async_main() -> None:
    cfg = load_config()
    logger.info("JackClaw starting...")

    app_id, app_secret = get_feishu_credentials(cfg)
    logger.info("Feishu app_id: %s", app_id[:8] + "...")

    client = Client.builder().app_id(app_id).app_secret(app_secret).log_level(LogLevel.INFO).build()

    data_dir = Path(cfg.get("data_dir", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    feishu_cfg = cfg.get("feishu", {})
    allowed_chats = feishu_cfg.get("allowed_chats", []) or []

    debug_cfg = cfg.get("debug", {})
    enable_test_api = debug_cfg.get("enable_test_api", False)
    test_api_port = debug_cfg.get("test_api_port", 9090)

    runner_cfg = cfg.get("runner", {})
    idle_timeout = runner_cfg.get("queue_idle_timeout_s", 300.0)

    session_mgr = SessionManager(data_dir=data_dir)
    sender = FeishuSender(client=client)

    runner = Runner(
        session_mgr=session_mgr,
        sender=sender,
        idle_timeout=idle_timeout,
    )

    loop = asyncio.get_running_loop()
    listener = FeishuListener(
        app_id=app_id,
        app_secret=app_secret,
        on_message=runner.dispatch,
        loop=loop,
        allowed_chats=allowed_chats if allowed_chats else None,
    )

    logger.info("Phase 1 ready")

    tasks = [asyncio.create_task(run_forever(listener), name="feishu-listener")]

    if enable_test_api:
        from jackclaw.api.test_server import create_test_app
        test_app = create_test_app(runner=runner, session_mgr=session_mgr)
        tasks.append(asyncio.create_task(_run_test_api(test_app, port=test_api_port), name="test-api"))

    await asyncio.gather(*tasks)


async def _run_test_api(app, host: str = "127.0.0.1", port: int = 9090) -> None:
    from aiohttp import web
    app_runner = web.AppRunner(app)
    await app_runner.setup()
    site = web.TCPSite(app_runner, host=host, port=port)
    await site.start()
    logger.info("TestAPI listening on http://%s:%d", host, port)
    try:
        await asyncio.Event().wait()
    finally:
        await app_runner.cleanup()


def main() -> None:
    setup_logging()
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("JackClaw stopped")


if __name__ == "__main__":
    main()
