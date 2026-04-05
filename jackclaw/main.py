"""
JackClaw 进程入口 - Phase 0

仅包含最小可运行骨架
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from jackclaw.config import load_config, get_feishu_credentials

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """初始化日志"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def async_main() -> None:
    """异步主函数"""
    cfg = load_config()
    logger.info("JackClaw starting...")
    
    app_id, app_secret = get_feishu_credentials(cfg)
    logger.info("Feishu app_id: %s", app_id[:8] + "...")
    
    logger.info("Phase 0 skeleton ready")
    await asyncio.Event().wait()


def main() -> None:
    setup_logging()
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("JackClaw stopped")


if __name__ == "__main__":
    main()
