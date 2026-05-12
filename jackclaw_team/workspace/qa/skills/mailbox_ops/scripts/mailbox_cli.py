"""mailbox_cli — 沙盒内 Agent 调用本地 CLI 操作团队邮箱."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 沙盒内挂载：/workspace → 宿主机 workspace/
# smoke 简化：去掉文件锁（单 agent 顺序执行场景），避免沙盒 user / 目录权限问题
import contextlib


@contextlib.contextmanager
def _locked(path: Path):
    """smoke no-op lock；生产可换 FileLock/fcntl."""
    yield


def _inbox_path(workspace: Path, project_id: str, role: str) -> Path:
    return workspace / "shared" / "projects" / project_id / "mailboxes" / f"{role}.json"


def _iso_utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _send(args) -> dict:
    import uuid
    inbox = _inbox_path(args.workspace, args.project_id, args.to)
    if not inbox.exists():
        return {"errcode": 1, "errmsg": f"inbox not found: {inbox}", "data": {}}
    msg_id = f"msg-{uuid.uuid4().hex[:8]}"
    msg = {
        "id": msg_id, "project_id": args.project_id,
        "from": getattr(args, "from"), "to": args.to,
        "type": args.type, "subject": args.subject, "content": args.content,
        "timestamp": _iso_utc_now(), "status": "unread", "processing_since": None,
    }
    with _locked(inbox):
        msgs = json.loads(inbox.read_text() or "[]")
        msgs.append(msg)
        inbox.write_text(json.dumps(msgs, ensure_ascii=False, indent=2))
    return {"errcode": 0, "errmsg": "success", "data": {"msg_id": msg_id}}


def _read(args) -> dict:
    inbox = _inbox_path(args.workspace, args.project_id, args.role)
    if not inbox.exists():
        return {"errcode": 1, "errmsg": f"inbox not found: {inbox}", "data": {}}
    snapshots = []
    with _locked(inbox):
        msgs = json.loads(inbox.read_text() or "[]")
        now = _iso_utc_now()
        changed = False
        for m in msgs:
            if m.get("status") == "unread":
                m["status"] = "in_progress"
                m["processing_since"] = now
                snapshots.append(dict(m))
                changed = True
        if changed:
            inbox.write_text(json.dumps(msgs, ensure_ascii=False, indent=2))
    return {"errcode": 0, "errmsg": "success", "data": {"messages": snapshots, "count": len(snapshots)}}


def _mark_done(args) -> dict:
    inbox = _inbox_path(args.workspace, args.project_id, args.role)
    with _locked(inbox):
        msgs = json.loads(inbox.read_text() or "[]")
        target = next((m for m in msgs if m["id"] == args.msg_id), None)
        if target is None:
            return {"errcode": 1, "errmsg": f"msg not found: {args.msg_id}", "data": {}}
        if target["status"] != "in_progress":
            return {"errcode": 1, "errmsg": f"not in_progress (cur={target['status']})", "data": {}}
        target["status"] = "done"
        inbox.write_text(json.dumps(msgs, ensure_ascii=False, indent=2))
    return {"errcode": 0, "errmsg": "success", "data": {"msg_id": args.msg_id}}


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("send")
    ps.add_argument("--workspace", type=Path, required=True)
    ps.add_argument("--project-id", required=True)
    ps.add_argument("--from", required=True, dest="from")
    ps.add_argument("--to", required=True)
    ps.add_argument("--type", required=True)
    ps.add_argument("--subject", required=True)
    ps.add_argument("--content", required=True)

    pr = sub.add_parser("read-inbox")
    pr.add_argument("--workspace", type=Path, required=True)
    pr.add_argument("--project-id", required=True)
    pr.add_argument("--role", required=True)

    pm = sub.add_parser("mark-done")
    pm.add_argument("--workspace", type=Path, required=True)
    pm.add_argument("--project-id", required=True)
    pm.add_argument("--role", required=True)
    pm.add_argument("--msg-id", required=True)

    args = p.parse_args()
    fn = {"send": _send, "read-inbox": _read, "mark-done": _mark_done}[args.cmd]
    out = fn(args)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if out.get("errcode", 0) == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
