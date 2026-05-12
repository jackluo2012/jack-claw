"""
main.py — JackClaw-Team 进程入口（29 课）
进程入口：build_agent_fn_map + register_heartbeats
启动顺序（对齐 DESIGN.md §附录 G main.py 骨架）：
1. 加载 config.yaml
2. 初始化日志
3. 构建 SessionManager + Sender(可选)
4. 为 4 角色构造 agent_fn (Manager 额外套 asyncio.Lock)
5. 构建 Runner(agent_fn_map) + CronService(dispatch_fn=runner.dispatch)
6. 注册 4 条 heartbeat（every=30s，first_delay 错峰 0/7/14/21）
7. 启动 Listener（可选）或仅跑服务进入事件循环
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from jackclaw_team.agents.build import build_team_agent_fn, wrap_with_lock
from jackclaw_team.cron import tasks_store
from jackclaw_team.cron.service import CronService
from jackclaw_team.models import SenderProtocol
from jackclaw_team.runner import Runner
from jackclaw_team.session.manager import SessionManager
logger = logging.getLogger(__name__)

ROLES = ("manager", "pm", "rd", "qa")
HEARTBEAT_INTERVAL_MS = 30_000
HEARTBEAT_STAGGER_MS = (0, 7_000, 14_000, 21_000)

def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"config.yaml not found at {config_path}")
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

def register_heartbeats(
    tasks_path: Path,
    *,
    interval_ms: int = HEARTBEAT_INTERVAL_MS,
    stagger_ms: tuple[int, ...] = HEARTBEAT_STAGGER_MS,
) -> None:
    """注册 4 个角色的 heartbeat（默认 30s 间隔，错峰 0/7/14/21s）."""
    for idx, role in enumerate(ROLES):
        tasks_store.schedule_heartbeat(
            tasks_path,
            role=role,
            interval_ms=interval_ms,
            first_delay_ms=stagger_ms[idx % len(stagger_ms)],
        )

def build_agent_fn_map(
    *,
    workspace_root: Path,
    ctx_dir: Path,
    sandbox_url: str,
    cron_tasks_path: Path,
    sender: SenderProtocol | None,
    db_dsn: str = "",
) -> dict[str, Any]:
    """为四个角色构造 agent_fn。

    **所有 4 个角色都套全局 team lock**（而非仅 Manager），因为 CrewAI 的
    @before_llm_call hook 注册到全局 event bus，并发时会跨角色串台。
    """
    m: dict[str, Any] = {}
    # **每次调用创建一把新锁**（避免多次 asyncio.run 跨 loop 共享同把 Lock 实例）
    team_lock = asyncio.Lock()
    for role in ROLES:
        fn = build_team_agent_fn(
            role=role,
            workspace_root=workspace_root,
            ctx_dir=ctx_dir,
            sender=sender,
            db_dsn=db_dsn,
            sandbox_url=sandbox_url,
            cron_tasks_path=cron_tasks_path,
        )
        # 所有 4 角色共享这一把 team_lock，避免 before_llm_call 跨实例串台
        fn = wrap_with_lock(fn, team_lock)
        m[role] = fn
    return m

async def build_runtime(
    *,
    workspace_root: Path,  # 工作空间根目录路径
    data_dir: Path,       # 数据存储目录路径
    ctx_dir: Path,        # 上下文目录路径
    sandbox_url: str,     # 沙箱环境的URL地址
    sender: SenderProtocol | None,  # 发送协议对象，可以为None
    db_dsn: str = "",     # 数据库连接字符串，默认为空字符串
    heartbeat_interval_ms: int = HEARTBEAT_INTERVAL_MS,  # 心跳间隔毫秒数，默认使用预设值
) -> tuple[Runner, CronService, SessionManager]:  # 返回一个包含Runner、CronService和SessionManager的元组
    """构建 Runner + CronService + SessionManager，启动 Cron."""
    workspace_root.mkdir(parents=True, exist_ok=True)
    ctx_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    cron_tasks_path = data_dir / "cron" / "tasks.json"
    cron_tasks_path.parent.mkdir(parents=True, exist_ok=True)

    session_mgr = SessionManager(data_dir=data_dir)
    agent_fn_map = build_agent_fn_map(
        workspace_root=workspace_root,
        ctx_dir=ctx_dir,
        sandbox_url=sandbox_url,
        cron_tasks_path=cron_tasks_path,
        sender=sender,
        db_dsn=db_dsn,
    )

    if sender is None:
        from jackclaw_team.api.capture_sender import CaptureSender

        sender = CaptureSender()

    runner = Runner(session_mgr=session_mgr, sender=sender, agent_fn_map=agent_fn_map)

    register_heartbeats(cron_tasks_path, interval_ms=heartbeat_interval_ms)
    cron_svc = CronService(data_dir=data_dir, dispatch_fn=runner.dispatch)
    await cron_svc.start()

    logger.info(
        "JackClaw-Team runtime ready. workspace=%s data=%s sandbox=%s",
        workspace_root, data_dir, sandbox_url,
    )
    return runner, cron_svc, session_mgr


async def async_main() -> None:
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--config", default="config.yaml", type=Path)
    parser.add_argument("--no-feishu", action="store_true", help="跳过飞书 Listener（仅 cron 驱动）")
    args = parser.parse_args()
    
    cfg = load_config(args.config)
    logging.basicConfig(
        level=os.environ.get("JACKCLAW_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    data_dir = Path(cfg.get("data_dir", "./data")).resolve()
    workspace_root = Path(cfg.get("memory", {}).get("workspace_dir", "./workspace")).resolve()
    ctx_dir = Path(cfg.get("memory", {}).get("ctx_dir", "./data/ctx")).resolve()
    sandbox_url = cfg.get("sandbox", {}).get("url", "http://localhost:8029/mcp")
    db_dsn = cfg.get("memory", {}).get("db_dsn", "")

    sender: SenderProtocol | None = None
    if not args.no_feishu:
        feishu_cfg = cfg.get("feishu", {})
        app_id = feishu_cfg.get("app_id", "")
        app_secret = feishu_cfg.get("app_secret", "")
        if app_id and app_secret:
            # 飞书客户端需要 app_id/app_secret 进行初始化，
            # 仅当配置完整时才构建 FeishuSender。
            from lark_oapi.client import Client, LogLevel

            from jackclaw_team.feishu.sender import FeishuSender

            client = (
                Client.builder()
                .app_id(app_id).app_secret(app_secret)
                .log_level(LogLevel.INFO).build()
            )
            sender = FeishuSender(client=client)

    # 构建运行时环境：Runner、CronService、SessionManager
    runner, cron_svc, _ = await build_runtime(
        workspace_root=workspace_root,
        data_dir=data_dir,
        ctx_dir=ctx_dir,
        sandbox_url=sandbox_url,
        sender=sender,
        db_dsn=db_dsn,
    )

    if args.no_feishu:
        logger.info("--no-feishu: skipping Listener; running Cron-only")
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            await cron_svc.stop()
        return

    # 生产模式：启动飞书 Listener
    if sender is None:
        raise RuntimeError("feishu credentials missing; use --no-feishu for cron-only mode")

    from jackclaw_team.feishu.listener import FeishuListener, run_forever  # type: ignore

    listener = FeishuListener(
        client=sender.client,  # type: ignore[attr-defined]
        dispatch_fn=runner.dispatch,
    )
    try:
        await run_forever(listener)
    finally:
        await cron_svc.stop()


def main() -> None:

    """
    主函数，用于启动异步程序
    该函数通过asyncio.run()来运行异步主函数async_main()
    """
    asyncio.run(async_main())  # 调用asyncio.run()运行异步主函数async_main()


if __name__ == "__main__":
    main()