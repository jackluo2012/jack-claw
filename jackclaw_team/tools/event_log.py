"""
event_log.py — append-only 事件流（DESIGN.md §11.4 + 附录 A）

对齐 v1.4/v1.5：
- JSON Lines 格式
- 字段：ts / seq / actor / action / payload（都必填）
- FileLock 保护 append（保证 seq 单调递增）
- ts: ISO 8601 UTC `+00:00` 后缀
- actor 固定 "manager"（仅 Manager 有权写）
- action 枚举校验（附录 A.3）
- read_events / tail_events 跳过损坏行
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from filelock import FileLock

from jackclaw_team.tools.mailbox import iso_utc_now

# 附录 A.3 完整枚举
VALID_ACTIONS = {
    # 项目生命周期
    "project_created", "archived",
    # 需求阶段
    "requirements_discovery_started", "requirements_coverage_assessed",
    "requirements_drafted",
    # checkpoint
    "checkpoint_requested", "checkpoint_reply_classified",
    "checkpoint_approved", "checkpoint_rejected",
    # 任务流转
    "assigned", "task_done_received", "revision_requested", "rd_delivered",
    # 评审
    "review_criteria_checked", "decided_insert_review",
    "review_requested", "review_received",
    # 交付
    "delivery_requested", "delivered",
    # 复盘进化 (v1.4)
    "retro_triggered",
    "retro_report_received",
    "retro_proposal_invalid",
    "retro_approved_by_manager",
    "retro_approved_by_human",
    "retro_rejected_by_human",
    # retro_applied_by_{role} 用通配，见下
    "retro_apply_failed",
    "task_quality_adjusted",
    "evolved",
    # 异常与自愈
    "error_alert_raised",
    "recovered_checkpoint_response",
    # SendToHuman 出站（L1 联动）
    "info_sent", "checkpoint_request_sent", "proposal_review_sent",
    "delivery_sent", "evolution_report_sent", "error_alert_sent",
}

_LOCK_SUFFIX = ".lock"


def _lock_path(events_path: Path) -> str:
    return str(events_path) + _LOCK_SUFFIX


def init_events(events_path: Path) -> None:
    """创建空 events.jsonl（幂等）."""
    events_path.parent.mkdir(parents=True, exist_ok=True)
    if not events_path.exists():
        events_path.write_text("")


def _is_valid_action(action: str) -> bool:
    if action in VALID_ACTIONS:
        return True
    # 允许 retro_applied_by_{role} 通配
    if action.startswith("retro_applied_by_"):
        role = action[len("retro_applied_by_"):]
        return role in {"manager", "pm", "rd", "qa"}
    return False


def _last_seq(events_path: Path) -> int:
    """读最后一行的 seq；空文件返回 0；最后一行损坏则查前一行。"""
    if not events_path.exists() or events_path.stat().st_size == 0:
        return 0
    # 从尾部往前找第一条合法 JSON
    with events_path.open("rb") as f:
        f.seek(0, 2)
        end = f.tell()
        # 简单一些：读整个文件拆行（对本课规模 <1000 条事件够用）
        f.seek(0)
        lines = f.read().decode("utf-8").splitlines()
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            return int(json.loads(line)["seq"])
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return 0


def append_event(
    events_path: Path,
    *,
    action: str,
    payload: dict,
    actor: str = "manager",
) -> int:
    """追加一条事件，返回分配的 seq。"""
    if not _is_valid_action(action):
        raise ValueError(f"unknown action: {action!r}")
    if actor != "manager":
        raise ValueError(
            f"actor must be 'manager' (events.jsonl single-writer rule); got {actor!r}"
        )

    events_path.parent.mkdir(parents=True, exist_ok=True)

    with FileLock(_lock_path(events_path)):
        seq = _last_seq(events_path) + 1
        entry = {
            "ts": iso_utc_now(),
            "seq": seq,
            "actor": actor,
            "action": action,
            "payload": payload,
        }
        line = json.dumps(entry, ensure_ascii=False)
        with events_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    return seq


def iter_events(events_path: Path) -> Iterator[dict]:
    """生成器按序 yield 所有合法事件（skip 损坏行）."""
    if not events_path.exists():
        return
    with events_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def read_events(events_path: Path) -> list[dict]:
    return list(iter_events(events_path))


def tail_events(events_path: Path, *, n: int) -> list[dict]:
    all_events = read_events(events_path)
    return all_events[-n:] if n < len(all_events) else all_events 