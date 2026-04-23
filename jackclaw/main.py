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
import yaml

from jackclaw.config import load_config, get_feishu_credentials
from jackclaw.llm.aliyun_llm import AliyunLLM
from jackclaw.agents.main_crew import build_agent_fn
from jackclaw.feishu.downloader import FeishuDownloader
from jackclaw.llm.factory import LLMFactory
from jackclaw.session.manager import SessionManager
from jackclaw.runner import Runner
from jackclaw.feishu.listener import FeishuListener, run_forever
from jackclaw.feishu.sender import FeishuSender
from jackclaw.sandbox.client import SandboxClient
from jackclaw.cleanup.service import CleanupService
from jackclaw.cron.service import CronService
from jackclaw.observability.metrics_server import start_metrics_server
from jackclaw.observability.logging_config import setup_logging
logger = logging.getLogger(__name__)


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(
            f"config.yaml not found at {config_path}. 请先复制 config.yaml.template 并填写配置。"
        )
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return data


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
    """
    异步主函数，负责初始化和启动JackClaw应用
    包括配置加载、客户端设置、服务初始化和任务运行
    """
    # 加载配置
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "config.yaml"
    cfg = _load_config(config_path)

    # 记录启动日志
    # ── 1. 日志初始化 ──────────────────────────────────────────────────────
    data_dir = Path(cfg.get("data_dir", "./data")).resolve()
    setup_logging(data_dir / "logs")
    logger.info("JackClaw starting...")

    # ── 2. 读取关键配置 ────────────────────────────────────────────────────
    

    # 创建并解析数据目录
    data_dir = Path(cfg.get("data_dir", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    # 创建工作区目录
    workspace_dir = data_dir / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    memory_cfg = cfg.get("memory", {})
    ctx_dir       = Path(memory_cfg.get("ctx_dir", "./data/ctx")).resolve()
    db_dsn        = memory_cfg.get("db_dsn", "")

    # 获取飞书配置
    feishu_cfg = cfg.get("feishu", {})
    # 允许的聊天列表
    allowed_chats = feishu_cfg.get("allowed_chats", []) or []

    # 获取代理配置
    agent_cfg = cfg.get("agent", {})
    # 设置模型
    model = agent_cfg.get("model", "qwen-plus")

    # 获取技能配置
    skills_cfg = cfg.get("skills", {})
    # 设置技能目录
    skills_dir = Path(skills_cfg.get("local_dir", "./skills")).resolve()

    # 获取沙盒配置
    sandbox_cfg = cfg.get("sandbox", {})
    # 设置沙盒超时时间
    sandbox_timeout = sandbox_cfg.get("timeout_s", 60)
    # 设置沙盒URL
    sandbox_url = sandbox_cfg.get("url", "http://localhost:8022/mcp")

    # 获取会话配置
    max_history_turns = cfg.get("session", {}).get("max_history_turns", 20)
    # 获取调试配置
    debug_cfg = cfg.get("debug", {})
    # 设置是否启用测试API
    enable_test_api = debug_cfg.get("enable_test_api", False)
    test_api_host = debug_cfg.get("test_api_host", "127.0.0.1")
    # 设置测试API端口
    test_api_port = debug_cfg.get("test_api_port", 9090)

    # 获取可观测性配置
    observability_cfg = cfg.get("observability", {})
    # 设置是否启用指标收集
    enable_metrics = observability_cfg.get("enable_metrics", False)
    # 设置指标收集端口
    metrics_port = observability_cfg.get("metrics_port", 9091)

    # 获取运行器配置
    runner_cfg = cfg.get("runner", {})
    # 设置队列空闲超时时间
    idle_timeout = runner_cfg.get("queue_idle_timeout_s", 300.0)
    # ── 3. 构建 Feishu HTTP Client ─────────────────────────────────────────

    # 获取飞书凭证
    app_id, app_secret = get_feishu_credentials(cfg)
    # 使用最新配置：添加超时和重试设置
    client = (Client.builder()
              .app_id(app_id)
              .app_secret(app_secret)
              .log_level(LogLevel.INFO)
              .build())
    
    # ── 4. 初始化核心服务 ───────────────────────────────────────────────────
    session_mgr = SessionManager(data_dir=data_dir)
    sender = FeishuSender(client=client)
    downloader = FeishuDownloader(client=client, data_dir=data_dir)
    cleanup_svc = CleanupService(data_dir=data_dir)    
    
    # 写入飞书凭证到沙盒 .config 目录（凭证不经过 LLM）
    cleanup_svc.write_feishu_credentials(app_id=app_id, app_secret=app_secret)
    
    # 写入百度千帆 API Key 到沙盒 .config 目录（支持 baidu_search Skill）
    baidu_api_key = cfg.get("baidu", {}).get("api_key", "") or os.environ.get("BAIDU_API_KEY", "")
    cleanup_svc.write_baidu_credentials(api_key=baidu_api_key)    
    
    # 启动时执行一次存储清理（清除历史残留）
    try:
        await cleanup_svc.sweep()
    except Exception:  # noqa: BLE001
        logger.warning("cleanup: startup sweep failed", exc_info=True)    
    
    # ── 5. 构建真实 agent_fn ────────────────────────────────────────────────
    workspace_dir.mkdir(parents=True, exist_ok=True)
    ctx_dir.mkdir(parents=True, exist_ok=True)



    # ── 5. 输出加载的 Skills 和 Tools 日志 ────────────────────────────────
    import yaml
    skills_config_path = repo_root / "jackclaw" / "skills" / "load_skills.yaml"
    if skills_config_path.exists():
        try:
            skills_data = yaml.safe_load(skills_config_path.read_text(encoding="utf-8"))
            skills_list = skills_data.get("skills", [])
            enabled_skills = [s for s in skills_list if s.get("enabled", True)]

            logger.info("=" * 60)
            logger.info("📦 已加载 %d 个 Skills:", len(enabled_skills))
            for skill in enabled_skills:
                skill_name = skill.get("name", "unknown")
                skill_type = skill.get("type", "task")
                logger.info("  - %s [%s]", skill_name, skill_type)
            logger.info("=" * 60)
        except Exception as e:
            logger.warning("Failed to load skills config for logging: %s", e)
    else:
        logger.warning("Skills config file not found: %s", skills_config_path)

    # 输出加载的 Tools 信息
    logger.info("🔧 已加载 Tools:")
    logger.info("  - SkillLoaderTool: 技能加载器（支持 %d 个技能）", len(enabled_skills) if 'enabled_skills' in locals() else 0)
    logger.info("  - IntermediateTool: 中间结果保存工具")

    agent_fn = build_agent_fn(
        sender=sender,
        workspace_dir=workspace_dir,
        ctx_dir=ctx_dir,
        db_dsn=db_dsn,
        max_history_turns=max_history_turns,
        sandbox_url=sandbox_url,
    )
    logger.info("✓ Agent 构建完成")

    # ── 6. 构建 Runner ──────────────────────────────────────────────────────
    runner = Runner(
        session_mgr=session_mgr,
        sender=sender,
        agent_fn=agent_fn,
        downloader=downloader,
        idle_timeout=idle_timeout,
    )
    # ── 7. CronService ──────────────────────────────────────────────────────
    (data_dir / "cron").mkdir(parents=True, exist_ok=True)
    cron_svc = CronService(data_dir=data_dir, dispatch_fn=runner.dispatch)
    await cron_svc.start()

    # ── 8. WebSocket Listener ───────────────────────────────────────────────
    loop = asyncio.get_running_loop()
    allowed_chats: list[str] = feishu_cfg.get("allowed_chats", []) or []
    listener = FeishuListener(
        app_id=app_id,
        app_secret=app_secret,
        on_message=runner.dispatch,
        loop=loop,
        allowed_chats=allowed_chats if allowed_chats else None,
    )

    # 启动飞书监听器（必须在 run_forever 之前调用）
    listener.start()
    logger.info("jackclaw ready. sandbox_url=%s, test_api=%s", sandbox_url, enable_test_api)

    # ── 9. 并行启动所有服务 ─────────────────────────────────────────────────
    tasks = [
        asyncio.create_task(run_forever(listener), name="feishu-listener"),
        asyncio.create_task(
            start_metrics_server(host="127.0.0.1", port=9100),
            name="metrics-server",
        ),
        asyncio.create_task(
            _daily_cleanup_loop(cleanup_svc),
            name="cleanup-scheduler",
        ),
    ]

    if enable_test_api:
        from jackclaw.api.capture_sender import CaptureSender  # noqa: PLC0415
        from jackclaw.api.test_server import create_test_app  # noqa: PLC0415

        # 💡 核心点：test runner 使用 CaptureSender，拦截 agent 回复供 HTTP 同步返回
        capture_sender = CaptureSender()
        test_runner = Runner(
            session_mgr=session_mgr,
            sender=capture_sender,
            agent_fn=agent_fn,
            downloader=downloader,
            idle_timeout=idle_timeout,
        )
        test_app = create_test_app(
            runner=test_runner,
            sender=capture_sender,
            session_mgr=session_mgr,
            workspace_dir=workspace_dir,
        )
        tasks.append(
            asyncio.create_task(
                _run_test_api(test_app, host=test_api_host, port=test_api_port),
                name="test-api",
            )
        )
        logger.info("TestAPI enabled: http://%s:%d", test_api_host, test_api_port)

    await asyncio.gather(*tasks)


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
    # 读取配置文件以获取 data_dir
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "config.yaml"
    cfg = _load_config(config_path)
    data_dir = Path(cfg.get("data_dir", "./data")).resolve()

    # 设置日志
    setup_logging(data_dir / "logs")

    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("JackClaw stopped")


if __name__ == "__main__":
    main()
