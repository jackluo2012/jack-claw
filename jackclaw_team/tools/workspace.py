"""
workspace.py — 共享工作区读写 + 权限校验

对齐 DESIGN.md §11.1 / §11.2 / §11.2.1（v1.3-P2-20 正则修复）+ §15.2（CreateProjectTool 完整清单）。

OWNER_BY_PREFIX 强制写权限；reviews/ 走独立正则校验；mailboxes/events.jsonl 禁止通过此接口写。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from filelock import FileLock


# v1.3-P2-20：严格白名单 + 强制 topic 后缀
REVIEWS_PATTERN = re.compile(
    r"^reviews/([a-z_]+)/(manager|pm|rd|qa)_([a-z0-9_]+)\.md$"
)

OWNER_BY_PREFIX: dict[str, set[str]] = {
    "needs/":   {"manager"},
    "design/":  {"pm"},
    "tech/":    {"rd"},
    "code/":    {"rd"},
    "qa/":      {"qa"},
}

# 必须通过专用 Tool 写，禁止 WriteShared
FORBIDDEN_PREFIXES = ("mailboxes/", "events.jsonl")


def _project_root(workspace_root: Path, project_id: str) -> Path:
    return workspace_root / "shared" / "projects" / project_id


def _check_path_traversal(rel_path: str) -> None:
    """阻止 `..` / 绝对路径等路径穿越尝试."""
    if rel_path.startswith("/") or rel_path.startswith("\\"):
        raise PermissionError(f"absolute path not allowed: {rel_path}")
    # 分隔符后的 `..` 段
    parts = re.split(r"[/\\]", rel_path)
    if ".." in parts:
        raise PermissionError(f"path traversal not allowed: {rel_path}")


def check_write(role: str, rel_path: str) -> None:
    """权限校验，违规抛 PermissionError。"""
    _check_path_traversal(rel_path)

    # 禁止目录
    for forbidden in FORBIDDEN_PREFIXES:
        if rel_path == forbidden or rel_path.startswith(forbidden):
            raise PermissionError(
                f"{rel_path} must be written via dedicated Tool (SendMail/AppendEvent), not WriteShared"
            )

    # reviews/ 独立校验
    if rel_path.startswith("reviews/"):
        m = REVIEWS_PATTERN.match(rel_path)
        if not m:
            raise PermissionError(
                f"reviews 文件名必须匹配 reviews/{{stage}}/{{reviewer}}_{{topic}}.md；"
                f"reviewer ∈ manager|pm|rd|qa，topic 必填；got {rel_path!r}"
            )
        _, reviewer, _ = m.groups()
        if reviewer != role:
            raise PermissionError(
                f"role={role} 不能以 reviewer={reviewer} 身份写评审文件"
            )
        return

    # Owner 前缀校验
    for prefix, owners in OWNER_BY_PREFIX.items():
        if rel_path.startswith(prefix):
            if role not in owners:
                raise PermissionError(
                    f"{role} cannot write {rel_path} (owner={owners})"
                )
            return

    raise PermissionError(f"unknown path prefix: {rel_path}")


def write_shared(
    workspace_root: Path,
    *,
    project_id: str,
    role: str,
    rel_path: str,
    content: str,
) -> None:
    check_write(role, rel_path)
    proj = _project_root(workspace_root, project_id)
    full = proj / rel_path
    # 💡 修复 H4：FileLock 保护并发写同文件（两个 review 同时写 reviews/xxx/*.md）
    full.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(full) + ".lock"):
        # 先写 tmp，再 rename，保证原子性
        tmp = full.with_suffix(full.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(full)


def read_shared(
    workspace_root: Path,
    *,
    project_id: str,
    role: str,  # 留着做审计用，当前无 ACL
    rel_path: str,
) -> str:
    _check_path_traversal(rel_path)
    proj = _project_root(workspace_root, project_id)
    full = proj / rel_path
    if not full.exists():
        raise FileNotFoundError(f"not found: {full}")
    return full.read_text(encoding="utf-8")


def init_project_tree(workspace_root: Path, *, project_id: str) -> None:
    """初始化一个项目的完整目录树（DESIGN.md §15.2 CreateProjectTool 规格）."""
    proj = _project_root(workspace_root, project_id)
    dirs = (
        "needs", "design", "tech", "code",
        "qa", "qa/defects", "reviews",
        "mailboxes", "logs/l2_task",
    )
    for d in dirs:
        (proj / d).mkdir(parents=True, exist_ok=True)

    # 4 邮箱 json + events.jsonl + state.lock
    from jackclaw_team.tools.mailbox import init_mailboxes
    from jackclaw_team.tools.event_log import init_events

    init_mailboxes(proj / "mailboxes", roles=["manager", "pm", "rd", "qa"])
    init_events(proj / "events.jsonl")
    (proj / "state.lock").touch()