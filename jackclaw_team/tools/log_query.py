"""
log_query.py — 统一日志查询 CLI（DESIGN.md v1.4 §16.6）

对齐 28 课《复盘机制重构》：self_retrospective Sub-Crew 通过 bash 调用本模块查询 L1/L2 日志。

子命令：
- stats     整体统计
- tasks     任务列表（可排序/限制）
- steps     某任务的 ReAct 步骤回放（从 L3 session raw.jsonl 读）
- l1        人类纠正记录搜索
- all-agents  全员聚合（Manager 的 team_retrospective 用）

所有子命令输出 JSON 到 stdout。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


def _iter_l2_entries(logs_root: Path) -> Iterable[dict]:
    """遍历所有 shared/projects/*/logs/l2_task/*.jsonl."""
    projects_dir = logs_root / "shared" / "projects"
    if not projects_dir.exists():
        return
    for proj in projects_dir.iterdir():
        if not proj.is_dir():
            continue
        l2_dir = proj / "logs" / "l2_task"
        if not l2_dir.exists():
            continue
        for jl in sorted(l2_dir.glob("*.jsonl")):
            for line in jl.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def _iter_l1_entries(logs_root: Path) -> Iterable[dict]:
    """遍历 shared/logs/l1_human/*.jsonl（跨项目永久）."""
    l1_dir = logs_root / "shared" / "logs" / "l1_human"
    if not l1_dir.exists():
        return
    for jl in sorted(l1_dir.glob("*.jsonl")):
        for line in jl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _within_days(entry_ts: str, days: int) -> bool:
    try:
        ts = datetime.fromisoformat(entry_ts)
    except ValueError:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return ts >= cutoff


def query_stats(logs_root: Path, *, agent_id: str, days: int) -> dict:
    """整体统计：task_count / avg_quality / failure_count / human_correction_count."""
    tasks = [e for e in _iter_l2_entries(logs_root)
             if e.get("role") == agent_id and _within_days(e["ts"], days)]
    count = len(tasks)
    quality_vals = [e["result_quality_estimate"] for e in tasks
                    if e.get("result_quality_estimate") is not None]
    avg = round(sum(quality_vals) / len(quality_vals), 3) if quality_vals else None
    failures = sum(1 for q in quality_vals if q < 0.5)
    human_corrections = sum(1 for e in _iter_l1_entries(logs_root)
                            if e.get("content", {}).get("classified_as") == "rejected"
                            and _within_days(e["ts"], days))
    return {
        "agent_id": agent_id,
        "period_days": days,
        "task_count": count,
        "avg_quality": avg,
        "failure_count": failures,
        "human_correction_count": human_corrections,
    }


def query_tasks(
    logs_root: Path,
    *,
    agent_id: str,
    days: int,
    sort: str | None = None,
    limit: int | None = None,
) -> dict:
    """任务列表，可按 quality_asc / quality_desc 排序，limit 截断."""
    tasks = [e for e in _iter_l2_entries(logs_root)
             if e.get("role") == agent_id and _within_days(e["ts"], days)]
    if sort == "quality_asc":
        tasks.sort(key=lambda e: (e.get("result_quality_estimate") or 1.0))
    elif sort == "quality_desc":
        tasks.sort(key=lambda e: -(e.get("result_quality_estimate") or 0.0))
    else:
        # 默认 ts asc
        tasks.sort(key=lambda e: e["ts"])
    if limit is not None:
        tasks = tasks[:limit]
    # 缩减字段，避免一次返回太多
    slim = [{
        "task_id": t["task_id"],
        "ts": t["ts"],
        "role": t["role"],
        "result_quality_estimate": t.get("result_quality_estimate"),
        "result_quality_breakdown": t.get("result_quality_breakdown"),
        "self_review_passed": t.get("self_review_passed"),
        "artifacts_produced": t.get("artifacts_produced", []),
        "task_desc": t.get("task_desc"),
        "errors": t.get("errors", []),
    } for t in tasks]
    return {"agent_id": agent_id, "period_days": days, "tasks": slim}


def query_l1(
    logs_root: Path,
    *,
    days: int,
    keyword: str | None = None,
) -> dict:
    """人类纠正记录搜索."""
    entries = []
    for e in _iter_l1_entries(logs_root):
        if not _within_days(e["ts"], days):
            continue
        if keyword:
            text = e.get("content", {}).get("user_text", "") or ""
            if keyword not in text:
                continue
        entries.append(e)
    return {"period_days": days, "keyword": keyword, "entries": entries}


def query_all_agents(logs_root: Path, *, days: int) -> dict:
    """聚合所有 role 的 stats + 识别瓶颈（最低 avg_quality）."""
    per_agent: dict[str, dict] = {}
    # 收集出现过的 role
    roles = set()
    for e in _iter_l2_entries(logs_root):
        if _within_days(e["ts"], days) and e.get("role"):
            roles.add(e["role"])
    for role in sorted(roles):
        per_agent[role] = query_stats(logs_root, agent_id=role, days=days)
    # bottleneck: avg_quality 最低的（过滤掉 None）
    scored = [(r, d["avg_quality"]) for r, d in per_agent.items()
              if d["avg_quality"] is not None]
    bottleneck = min(scored, key=lambda x: x[1])[0] if scored else None
    return {"period_days": days, "per_agent": per_agent, "bottleneck": bottleneck}


def query_steps(session_raw: Path, *, task_id: str, only_failed: bool = False) -> dict:
    """读 L3 session raw.jsonl，过滤某个 task_id 的 ReAct 步骤."""
    if not session_raw.exists():
        return {"task_id": task_id, "steps": []}
    steps = []
    for line in session_raw.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("task_id") != task_id:
            continue
        if only_failed and not entry.get("failed"):
            continue
        steps.append(entry)
    return {"task_id": task_id, "only_failed": only_failed, "steps": steps}


# ---------- CLI 入口 ----------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="log_query",
                                     description="Unified log query CLI for self/team retrospective")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _common(p):
        p.add_argument("--logs-root", type=Path, default=Path("workspace"),
                       help="workspace root（默认 workspace/）")

    p_stats = sub.add_parser("stats")
    _common(p_stats)
    p_stats.add_argument("--agent-id", required=True)
    p_stats.add_argument("--days", type=int, default=7)

    p_tasks = sub.add_parser("tasks")
    _common(p_tasks)
    p_tasks.add_argument("--agent-id", required=True)
    p_tasks.add_argument("--days", type=int, default=7)
    p_tasks.add_argument("--sort", choices=["quality_asc", "quality_desc"])
    p_tasks.add_argument("--limit", type=int)

    p_l1 = sub.add_parser("l1")
    _common(p_l1)
    p_l1.add_argument("--days", type=int, default=7)
    p_l1.add_argument("--keyword")

    p_all = sub.add_parser("all-agents")
    _common(p_all)
    p_all.add_argument("--days", type=int, default=7)

    p_steps = sub.add_parser("steps")
    _common(p_steps)
    p_steps.add_argument("--session-raw", type=Path, required=True)
    p_steps.add_argument("--task-id", required=True)
    p_steps.add_argument("--only-failed", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "stats":
        out = query_stats(args.logs_root, agent_id=args.agent_id, days=args.days)
    elif args.cmd == "tasks":
        out = query_tasks(args.logs_root, agent_id=args.agent_id, days=args.days,
                          sort=args.sort, limit=args.limit)
    elif args.cmd == "l1":
        out = query_l1(args.logs_root, days=args.days, keyword=args.keyword)
    elif args.cmd == "all-agents":
        out = query_all_agents(args.logs_root, days=args.days)
    elif args.cmd == "steps":
        out = query_steps(args.session_raw, task_id=args.task_id,
                          only_failed=args.only_failed)
    else:
        raise SystemExit(f"unknown cmd: {args.cmd}")
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())