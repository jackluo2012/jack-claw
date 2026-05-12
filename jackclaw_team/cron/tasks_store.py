"""
tasks_store.py — 宿主机侧 cron tasks.json 函数级 API.

对齐 DESIGN.md v1.5 §7.1 / §13.4 / §15.2（SendMailTool auto-register at wake）:
- 不改 CronService API
- write-then-rename 原子写入，CronService 通过 mtime/size 检测热重载
- 供 SendMailTool 调用以注册 `at=now+1s` 即时唤醒
"""
from __future__ import annotations

import contextlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from filelock import FileLock

def _now_ms() -> int:

    """
    获取当前时间戳，单位为毫秒
    
    Returns:
        int: 当前时间的毫秒时间戳
    """
    return int(time.time() * 1000)  # 将秒级时间戳转换为毫秒级时间戳


def _lock_path(tasks_path: Path) -> str:
    return str(tasks_path) + ".lock"


@contextlib.contextmanager
def _locked(tasks_path: Path):
    """FileLock around the tasks.json load-modify-dump sequence (修复 H2)."""
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(_lock_path(tasks_path)):
        yield


def _load_store(tasks_path: Path) -> dict[str, Any]:
    if not tasks_path.exists():
        return {"version": 1, "jobs": []}
    data = json.loads(tasks_path.read_text(encoding="utf-8") or '{"version":1,"jobs":[]}')
    if isinstance(data, list):
        return {"version": 1, "jobs": list(data)}
    jobs = data.get("jobs", [])
    if not isinstance(jobs, list):
        jobs = []
    return {"version": int(data.get("version", 1)), "jobs": list(jobs)}


def _dump_store(tasks_path: Path, store: dict[str, Any]) -> None:
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tasks_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(tasks_path)


def create_job(
    tasks_path: Path,  # 任务路径，用于存储任务数据
    *,
    name: str,  # 任务名称
    routing_key: str,  # 消息路由键
    message: str,  # 消息内容
    schedule_kind: str = "at",  # 调度类型，默认为"at"
    at_ms: int | None = None,  # 在特定时间执行（毫秒时间戳）
    every_ms: int | None = None,  # 每隔多少毫秒执行一次
    expr: str | None = None,  # cron表达式
    tz: str | None = None,  # 时区信息
    delete_after_run: bool = True,
) -> str:
    """创建一个 cron job，返回 job_id。"""
    # 检查调度类型是否有效
    if schedule_kind not in {"at", "every", "cron"}:
        raise ValueError(f"invalid schedule_kind: {schedule_kind!r}")
    # 如果是"at"类型且未指定时间，则默认设置为当前时间+1秒
    if schedule_kind == "at" and at_ms is None:
        at_ms = _now_ms() + 1000  # 默认 now+1s
    if schedule_kind == "every" and every_ms is None:
        raise ValueError("every_ms is required for schedule_kind=every")
    if schedule_kind == "cron" and not expr:
        raise ValueError("expr is required for schedule_kind=cron")

    with _locked(tasks_path):
        store = _load_store(tasks_path)
        now_ms = _now_ms()
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        job: dict[str, Any] = {
            "id": job_id,
            "name": name,
            "enabled": True,
            "schedule": {
                "kind": schedule_kind,
                "at_ms": at_ms if schedule_kind == "at" else None,
                "every_ms": every_ms if schedule_kind == "every" else None,
                "expr": expr if schedule_kind == "cron" else None,
                "tz": tz if schedule_kind == "cron" else None,
            },
            "payload": {"routing_key": routing_key, "message": message},
            "state": {
                "next_run_at_ms": None,
                "every_ms": every_ms if schedule_kind == "every" else None,  # "every"类型的间隔  # "cron"类型的表达式
                "expr": expr if schedule_kind == "cron" else None,  # 时区信息
                "last_error": None,
            },
            "created_at_ms": now_ms,
            "updated_at_ms": now_ms,
            "delete_after_run": delete_after_run,
        }
        store["jobs"].append(job)
        _dump_store(tasks_path, store)
    return job_id


def schedule_wake(
    tasks_path: Path,
    *,
    role: str,
    reason: str = "new_mail",
    delay_ms: int = 1000,
    project_id: str = "",
) -> str:
    """注册一次性 team:{role} 唤醒（at=now+delay_ms，delete_after_run=True）.

    project_id 会拼进消息 payload，Agent 读到后可直接 read_inbox(project_id).

    💡 修复 C3：如果已有同 (role, project_id, reason) 的未到期 at-wake job，
    直接返回它的 id，避免 send_mail 循环导致 tasks.json 无限膨胀 + wake storm.
    """
    tag = f":{project_id}" if project_id else ""
    target_msg = f"__wake__:{reason}{tag}"
    target_rk = f"team:{role}"
    # 去重：查找同 routing_key+message 且未到期的 at job
    with _locked(tasks_path):
        now_ms = _now_ms()
        store = _load_store(tasks_path)
        for j in store["jobs"]:
            if (j.get("payload", {}).get("routing_key") == target_rk
                    and j.get("payload", {}).get("message") == target_msg
                    and j.get("schedule", {}).get("kind") == "at"
                    and j.get("delete_after_run", False)
                    and (j.get("schedule", {}).get("at_ms") or 0) > now_ms):
                return j["id"]  # 已有 pending 同类 wake → 复用
    return create_job(
        tasks_path,
        name=f"wake-{role}-{reason}-{_now_ms()}",
        routing_key=f"team:{role}",
        message=f"__wake__:{reason}{tag}",
        schedule_kind="at",
        at_ms=_now_ms() + delay_ms,
        delete_after_run=True,
    )


def schedule_heartbeat(
    tasks_path: Path,
    *,
    role: str,
    interval_ms: int = 30_000,
    first_delay_ms: int = 0,
) -> str:
    """注册 every heartbeat（不自删）."""
    store = _load_store(tasks_path)
    now_ms = _now_ms()
    job_id = f"heartbeat-{role}"
    # 若已存在同名 heartbeat 则替换
    store["jobs"] = [j for j in store["jobs"] if j.get("id") != job_id]
    job: dict[str, Any] = {
        "id": job_id,
        "name": f"heartbeat-{role}",
        "enabled": True,
        "schedule": {
            "kind": "every",
            "at_ms": None,
            "every_ms": interval_ms,
            "expr": None,
            "tz": None,
        },
        "payload": {
            "routing_key": f"team:{role}",
            "message": "__wake__:heartbeat",
        },
        "state": {
            "next_run_at_ms": now_ms + first_delay_ms,
            "last_run_at_ms": None,
            "last_status": None,
            "last_error": None,
        },
        "created_at_ms": now_ms,
        "updated_at_ms": now_ms,
        "delete_after_run": False,
    }
    store["jobs"].append(job)
    _dump_store(tasks_path, store)
    return job_id


def list_jobs(tasks_path: Path) -> list[dict]:
    return list(_load_store(tasks_path)["jobs"])


def delete_job(tasks_path: Path, *, job_id: str) -> bool:
    store = _load_store(tasks_path)
    before = len(store["jobs"])
    store["jobs"] = [j for j in store["jobs"] if j.get("id") != job_id]
    if len(store["jobs"]) == before:
        return False
    _dump_store(tasks_path, store)
    return True