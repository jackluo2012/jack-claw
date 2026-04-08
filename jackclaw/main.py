"""
JackClaw 主入口

这是 JackClaw 飞书工作助手的启动入口，负责：
- 加载配置文件
- 初始化各组件（LLM、Agent、Session、WebSocket）
- 启动消息处理循环

架构概览：

    飞书服务器 <--WebSocket--> FeishuListener
                                      |
                                      v
                               InboundMessage
                                      |
                                      v
    SessionManager <--> Runner <--> MainAgent <--> AliyunLLM
                           |
                           v
                    FeishuSender --> 飞书 API

Phase 3 功能：
- Skill 加载器：从 skills 目录加载技能定义
- 集成通义千问 LLM
- 完整的消息处理流水线

运行方式：
    python -m jackclaw.main

环境变量（必须）：
    FEISHU_APP_ID: 飞书应用 ID
    FEISHU_APP_SECRET: 飞书应用密钥
    QWEN_API_KEY: 通义千问 API Key
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from lark_oapi.client import Client, LogLevel

from jackclaw.config import load_config, get_feishu_credentials
from jackclaw.llm.aliyun_llm import AliyunLLM
from jackclaw.agents.main_agent import MainAgent
from jackclaw.session.manager import SessionManager
from jackclaw.runner import Runner
from jackclaw.feishu.listener import FeishuListener, run_forever
from jackclaw.feishu.sender import FeishuSender

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """配置日志格式"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def async_main() -> None:
    """
    异步主函数
    
    组件初始化顺序：
    1. 加载配置文件
    2. 创建飞书 API Client
    3. 初始化 LLM 适配器
    4. 创建 Agent
    5. 创建 Session 管理器
    6. 创建消息发送器
    7. 创建 Runner（执行引擎）
    8. 启动 WebSocket 监听器
    """
    # 加载配置
    cfg = load_config()
    logger.info("JackClaw starting...")

    # 飞书 API Client
    app_id, app_secret = get_feishu_credentials(cfg)
    client = Client.builder() \
        .app_id(app_id) \
        .app_secret(app_secret) \
        .log_level(LogLevel.INFO) \
        .build()

    # 数据目录
    data_dir = Path(cfg.get("data_dir", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    # 飞书配置
    feishu_cfg = cfg.get("feishu", {})
    allowed_chats = feishu_cfg.get("allowed_chats", []) or []

    # Agent 配置
    agent_cfg = cfg.get("agent", {})
    model = agent_cfg.get("model", "qwen-plus")

    # Skills 配置
    skills_cfg = cfg.get("skills", {})
    skills_dir = Path(skills_cfg.get("local_dir", "./skills")).resolve()

    # 调试配置
    debug_cfg = cfg.get("debug", {})
    enable_test_api = debug_cfg.get("enable_test_api", False)
    test_api_port = debug_cfg.get("test_api_port", 9090)

    # Runner 配置
    runner_cfg = cfg.get("runner", {})
    idle_timeout = runner_cfg.get("queue_idle_timeout_s", 300.0)

    # 初始化 LLM
    qwen_api_key = os.environ.get("QWEN_API_KEY", "")
    if not qwen_api_key:
        logger.warning("QWEN_API_KEY not set")
    llm = AliyunLLM(model=model, api_key=qwen_api_key)

    # 初始化 Agent
    agent = MainAgent(
        llm=llm,
        skills_dir=skills_dir if skills_dir.exists() else None,
    )
    logger.info("Agent initialized, skills_dir=%s", skills_dir)

    # 核心组件
    session_mgr = SessionManager(data_dir=data_dir)
    sender = FeishuSender(client=client)
    runner = Runner(
        session_mgr=session_mgr,
        sender=sender,
        agent_fn=agent.run,
        idle_timeout=idle_timeout,
    )

    # WebSocket 监听器
    loop = asyncio.get_running_loop()
    listener = FeishuListener(
        app_id=app_id,
        app_secret=app_secret,
        on_message=runner.dispatch,
        loop=loop,
        allowed_chats=allowed_chats if allowed_chats else None,
    )

    logger.info("Phase 3 ready")

    # 启动任务
    tasks = [
        asyncio.create_task(run_forever(listener), name="feishu-listener"),
    ]

    # 可选：TestAPI（本地调试）
    if enable_test_api:
        from jackclaw.api.test_server import create_test_app
        test_app = create_test_app(runner=runner, session_mgr=session_mgr)
        tasks.append(
            asyncio.create_task(_run_test_api(test_app, port=test_api_port), name="test-api")
        )

    # 等待所有任务（通常永不返回，除非被中断）
    await asyncio.gather(*tasks)


async def _run_test_api(app, host: str = "127.0.0.1", port: int = 9090) -> None:
    """
    运行 TestAPI HTTP 服务
    
    提供本地调试接口：
    - POST /api/test/message: 模拟发送消息
    
    Args:
        app: aiohttp Application
        host: 监听地址
        port: 监听端口
    """
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
    """
    主入口
    
    处理信号和异常，确保优雅退出。
    """
    setup_logging()
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("JackClaw stopped")
    except Exception:
        logger.exception("JackClaw crashed")
        raise


if __name__ == "__main__":
    main()
