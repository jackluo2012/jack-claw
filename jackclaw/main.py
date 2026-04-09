"""
JackClaw 进程入口 - Phase 5

包含：
- CronService 定时任务
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from lark_oapi.client import Client, LogLevel

from jackclaw.config import load_config, get_feishu_credentials
from jackclaw.llm.aliyun_llm import AliyunLLM
from jackclaw.agents.main_crew import build_agent_fn
from jackclaw.feishu.downloader import FeishuDownloader
from jackclaw.session.manager import SessionManager
from jackclaw.runner import Runner
from jackclaw.feishu.listener import FeishuListener, run_forever
from jackclaw.feishu.sender import FeishuSender
from jackclaw.sandbox.client import SandboxClient
from jackclaw.cleanup.service import CleanupService
from jackclaw.cron.service import CronService
from jackclaw.observability.metrics_server import start_metrics_server

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def _daily_cleanup_loop(cleanup_svc: CleanupService) -> None:
    import datetime
    import zoneinfo
    tz = zoneinfo.ZoneInfo("Asia/Shanghai")
    while True:
        now = datetime.datetime.now(tz)
        next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += datetime.timedelta(days=1)
        sleep_s = (next_run - now).total_seconds()
        await asyncio.sleep(sleep_s)
        try:
            await cleanup_svc.sweep()
        except Exception:
            logger.warning("Daily cleanup failed", exc_info=True)


async def async_main() -> None:
    cfg = load_config()
    logger.info("JackClaw starting...")

    app_id, app_secret = get_feishu_credentials(cfg)
    # 使用最新配置：添加超时和重试设置
    client = (Client.builder()
              .app_id(app_id)
              .app_secret(app_secret)
              .log_level(LogLevel.INFO)
              .build())

    data_dir = Path(cfg.get("data_dir", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir = data_dir / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    feishu_cfg = cfg.get("feishu", {})
    allowed_chats = feishu_cfg.get("allowed_chats", []) or []

    agent_cfg = cfg.get("agent", {})
    model = agent_cfg.get("model", "qwen-plus")

    skills_cfg = cfg.get("skills", {})
    skills_dir = Path(skills_cfg.get("local_dir", "./skills")).resolve()

    sandbox_cfg = cfg.get("sandbox", {})
    sandbox_timeout = sandbox_cfg.get("timeout_s", 60)
    sandbox_url = sandbox_cfg.get("url", "http://localhost:8022/mcp")

    max_history_turns = cfg.get("session", {}).get("max_history_turns", 20)

    debug_cfg = cfg.get("debug", {})
    enable_test_api = debug_cfg.get("enable_test_api", False)
    test_api_port = debug_cfg.get("test_api_port", 9090)

    observability_cfg = cfg.get("observability", {})
    enable_metrics = observability_cfg.get("enable_metrics", False)
    metrics_port = observability_cfg.get("metrics_port", 9091)

    runner_cfg = cfg.get("runner", {})
    idle_timeout = runner_cfg.get("queue_idle_timeout_s", 300.0)

    # LLM
    qwen_api_key = os.environ.get("QWEN_API_KEY", "")
    if not qwen_api_key:
        logger.warning("QWEN_API_KEY not set")
    llm = AliyunLLM(model=model, api_key=qwen_api_key)
    
    # Sandbox
    sandbox = SandboxClient(workspace_dir=workspace_dir, timeout=sandbox_timeout)

    # Core
    session_mgr = SessionManager(data_dir=data_dir)
    sender = FeishuSender(client=client)
    downloader = FeishuDownloader(client=client, data_dir=data_dir)
    cleanup_svc = CleanupService(data_dir=data_dir)

    # Agent
    agent_fn = build_agent_fn(
        model=model,
        sender=sender,
        max_history_turns=max_history_turns,
        sandbox_url=sandbox_url,
    )
    runner = Runner(
        session_mgr=session_mgr,
        sender=sender,
        agent_fn=agent_fn,
        downloader=downloader,
        idle_timeout=idle_timeout,
    )

    # CronService
    cron_svc = CronService(data_dir=data_dir, dispatch_fn=runner.dispatch)
    await cron_svc.start()

    # Startup cleanup
    # 写入飞书凭证到沙盒 .config 目录（凭证不经过 LLM）
    cleanup_svc.write_feishu_credentials(app_id=app_id, app_secret=app_secret)

    try:
        await cleanup_svc.sweep()
    except Exception:
        logger.warning("Startup cleanup failed", exc_info=True)

    loop = asyncio.get_running_loop()
    # 接收inbound消息
    listener = FeishuListener(
        app_id=app_id, app_secret=app_secret, on_message=runner.dispatch,
        loop=loop,
        allowed_chats=allowed_chats if allowed_chats else None,
    )
    listener.start()

    logger.info("Phase 5 ready")

    tasks = [
        asyncio.create_task(run_forever(listener), name="feishu-listener"),
        asyncio.create_task(_daily_cleanup_loop(cleanup_svc), name="cleanup"),
    ]
    if enable_metrics:
        tasks.append(asyncio.create_task(start_metrics_server(port=metrics_port), name="metrics-server"))
        logger.info("Metrics server enabled on port %d", metrics_port)
    if enable_test_api:
        from jackclaw.api.test_server import create_test_app
        test_app = create_test_app(runner=runner, session_mgr=session_mgr)
        tasks.append(asyncio.create_task(_run_test_api(test_app, port=test_api_port), name="test-api"))

    try:
        await asyncio.gather(*tasks)
    finally:
        await cron_svc.stop()


async def _run_test_api(app, host: str = "127.0.0.1", port: int = 9090) -> None:
    from aiohttp import web
    app_runner = web.AppRunner(app)
    await app_runner.setup()
    site = web.TCPSite(app_runner, host=host, port=port)
    await site.start()
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
