"""
mailbox.py — 团队内文件邮箱 (26 课三态状态机 + 29 课 project_id)

对齐 DESIGN.md v1.5 §11.3 规范：
- 位置：`workspace/shared/projects/{pid}/mailboxes/{role}.json`
- FileLock 保护 read-modify-write
- 三态：unread → in_progress → done
- timestamp: ISO 8601 UTC `+00:00` 后缀（v1.3-P0-6）
- id 格式：`^msg-[0-9a-f]{8}$`
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from filelock import FileLock

# 附录 B：from/to 允许的值
VALID_ROLES = {"manager", "pm", "rd", "qa"}
VALID_FROM_EXTRA = {"human", "feishu_bridge"}  # 特殊 from
VALID_TYPES = {
    "task_assign", "task_done", "review_request", "review_done",
    "clarification_request", "clarification_answer",
    "error_alert", "checkpoint_response",
    "retro_trigger", "retro_report",
    "retro_approved", "retro_rejected",
    "retro_applied", "retro_apply_failed",
}

ID_PATTERN = re.compile(r"^msg-[0-9a-f]{8}$")

def iso_utc_now() -> str:
    """ISO 8601 UTC with +00:00 suffix（v1.3-P0-6 规范）."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _inbox_path(mailbox_dir: Path, role: str) -> Path:
    return mailbox_dir / f"{role}.json"

def _lock_path(mailbox_dir: Path, role: str) -> Path:
    return mailbox_dir / f"{role}.json.lock"

def init_mailboxes(mailbox_dir: Path, roles: Iterable[str]) -> None:
    """初始化 mailboxes 目录：为每个 role 创建空 json 数组。幂等。"""
    mailbox_dir.mkdir(parents=True, exist_ok=True)
    for role in roles:
        p = _inbox_path(mailbox_dir, role)
        if not p.exists():
            p.write_text("[]")

def send_mail(
    mailbox_dir: Path,
    *,
    to: str,
    from_: str,
    type_: str,
    subject: str,
    content: str | dict,
    project_id: str,
) -> str:
    """写入一条 unread 消息到 to 的 inbox，返回 msg_id。FileLock 保护 read-modify-write。"""
    if to not in VALID_ROLES:
        raise ValueError(f"invalid recipient role: {to!r}")
    if from_ not in VALID_ROLES | VALID_FROM_EXTRA:
        raise ValueError(f"invalid sender role: {from_!r}")
    if type_ not in VALID_TYPES:
        raise ValueError(f"invalid type: {type_!r}")

    inbox = _inbox_path(mailbox_dir, to)
    if not inbox.exists():
        raise FileNotFoundError(f"mailbox not initialized: {inbox}")

    msg_id = f"msg-{uuid.uuid4().hex[:8]}"
    msg = {
        "id": msg_id,
        "project_id": project_id,
        "from": from_,
        "to": to,
        "type": type_,
        "subject": subject,
        "content": content,
        "timestamp": iso_utc_now(),
        "status": "unread",
        "processing_since": None,
    }

    with FileLock(str(_lock_path(mailbox_dir, to))):
        messages = json.loads(inbox.read_text() or "[]")
        messages.append(msg)
        inbox.write_text(json.dumps(messages, ensure_ascii=False, indent=2))

    return msg_id


def read_inbox(mailbox_dir: Path, *, role: str) -> list[dict]:
    """
    读取 role 的所有 unread 消息，原子地把状态改为 in_progress，返回 **快照副本**。
    调用方对返回值的修改不影响磁盘内容。
    """
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role!r}")

    inbox = _inbox_path(mailbox_dir, role)
    if not inbox.exists():
        raise FileNotFoundError(f"mailbox not initialized: {inbox}")

    snapshot: list[dict] = []
    with FileLock(str(_lock_path(mailbox_dir, role))):
        messages = json.loads(inbox.read_text() or "[]")
        now = iso_utc_now()
        changed = False
        for m in messages:
            if m.get("status") == "unread":
                m["status"] = "in_progress"
                m["processing_since"] = now
                # 返回快照副本：dict() 深拷贝 1 层足够，嵌套 dict 也做一次
                snap = {k: (dict(v) if isinstance(v, dict) else v) for k, v in m.items()}
                snapshot.append(snap)
                changed = True
        if changed:
            inbox.write_text(json.dumps(messages, ensure_ascii=False, indent=2))

    return snapshot


def mark_done(mailbox_dir: Path, *, role: str, msg_id: str) -> None:
    """把 in_progress 状态的消息改为 done。拒绝其他状态。"""
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role!r}")

    inbox = _inbox_path(mailbox_dir, role)
    with FileLock(str(_lock_path(mailbox_dir, role))):
        messages = json.loads(inbox.read_text() or "[]")
        target = next((m for m in messages if m["id"] == msg_id), None)
        if target is None:
            raise KeyError(f"msg not found: {msg_id}")
        if target["status"] != "in_progress":
            raise ValueError(f"msg {msg_id} is not in_progress (current={target['status']})")
        target["status"] = "done"
        inbox.write_text(json.dumps(messages, ensure_ascii=False, indent=2))


def reset_stale(mailbox_dir: Path, *, role: str, timeout_sec: int) -> int:
    """
    把 processing_since 超过 timeout_sec 的 in_progress 消息恢复为 unread。
    返回被重置的消息数。
    """
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role!r}")

    inbox = _inbox_path(mailbox_dir, role)
    now = datetime.now(timezone.utc)
    reset_count = 0
    with FileLock(str(_lock_path(mailbox_dir, role))):
        messages = json.loads(inbox.read_text() or "[]")
        for m in messages:
            if m.get("status") != "in_progress":
                continue
            ps = m.get("processing_since")
            if not ps:
                continue
            age = (now - datetime.fromisoformat(ps)).total_seconds()
            if age > timeout_sec:
                m["status"] = "unread"
                m["processing_since"] = None
                reset_count += 1
        if reset_count:
            inbox.write_text(json.dumps(messages, ensure_ascii=False, indent=2))
    return reset_count