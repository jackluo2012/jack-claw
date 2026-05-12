"""
team_tools.py — 29 课团队协作 Python Tools (CrewAI BaseTool 子类)

对齐 DESIGN.md v1.5 §15.2 / §15.3：
- 所有 Tool 都是宿主机进程内直接操作文件，不走沙盒
- Manager 独占：CreateProjectTool / AppendEventTool / SendToHumanTool
- 全角色共享：SendMailTool / ReadInboxTool / MarkDoneTool / ReadSharedTool / WriteSharedTool
- SendMailTool 发完邮件自动注册 at=now+1s cron wake → 收件角色被唤醒
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from jackclaw_team.cron import tasks_store
from jackclaw_team.models import SenderProtocol
from jackclaw_team.tools import event_log, mailbox, workspace

logger = logging.getLogger(__name__)

_PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _project_root(workspace_root: Path, project_id: str) -> Path:
    return workspace_root / "shared" / "projects" / project_id


# ── SendMailTool ────────────────────────────────────────────────────────────


class SendMailInput(BaseModel):
    to: str = Field(..., description="收件角色：manager/pm/rd/qa")
    type: str = Field(..., description="邮件类型（附录 B）：task_assign/task_done/review_request/...")
    subject: str = Field(..., description="一行标题，严格语法 `^.*\\(第 (\\d+) 轮\\)$` 用于 revision")
    content: str | dict = Field(..., description="正文；建议结构化 JSON；task_done 必须带 self_score")
    project_id: str = Field(..., description="项目 ID（小写字母+数字+下划线+中划线）")


class SendMailTool(BaseTool):
    """发送团队邮件，并自动注册 at=now+1s 唤醒收件角色."""

    name: str = "send_mail"
    description: str = (
        "向团队成员（manager/pm/rd/qa）发送一条邮件。必填字段：to/type/subject/content/project_id。"
        "发送后自动唤醒收件角色。返回 JSON {msg_id, scheduled_wake}. "
        "用于任务分派、任务完成回执、评审请求、需求澄清等所有角色间协作。"
    )
    args_schema: type[BaseModel] = SendMailInput

    _workspace_root: Path = PrivateAttr()
    _cron_tasks_path: Path = PrivateAttr()
    _from_role: str = PrivateAttr()

    def __init__(
        self,
        *,
        workspace_root: Path,
        cron_tasks_path: Path,
        from_role: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._workspace_root = workspace_root
        self._cron_tasks_path = cron_tasks_path
        self._from_role = from_role

    def _run(
        self,
        to: str,
        type: str,  # noqa: A002 — 与邮件 schema 对齐
        subject: str,
        content: str | dict,
        project_id: str,
        **_: Any,
    ) -> str:
        if not _PROJECT_ID_RE.match(project_id):
            return json.dumps(
                {"errcode": 1, "errmsg": f"invalid project_id: {project_id!r}"},
                ensure_ascii=False,
            )
        proj = _project_root(self._workspace_root, project_id)
        mailbox_dir = proj / "mailboxes"
        try:
            msg_id = mailbox.send_mail(
                mailbox_dir,
                to=to,
                from_=self._from_role,
                type_=type,
                subject=subject,
                content=content,
                project_id=project_id,
            )
            # 自动注册 at=now+1s wake，**project_id 拼进 wake 消息**让收件 Agent 直接知道要读哪个邮箱
            job_id = tasks_store.schedule_wake(
                self._cron_tasks_path,
                role=to, reason="new_mail", delay_ms=1000,
                project_id=project_id,
            )
            return json.dumps(
                {
                    "errcode": 0,
                    "msg_id": msg_id,
                    "scheduled_wake": job_id,
                    "to": to,
                    "type": type,
                },
                ensure_ascii=False,
            )
        except Exception as exc:
            logger.exception("send_mail failed")
            return json.dumps(
                {"errcode": 1, "errmsg": str(exc)},
                ensure_ascii=False,
            )


# ── ReadInboxTool ───────────────────────────────────────────────────────────


class ReadInboxInput(BaseModel):
    project_id: str = Field(..., description="项目 ID")


class ReadInboxTool(BaseTool):
    """读取本角色收件箱中 unread 消息（自动转 in_progress 并返回快照）."""

    name: str = "read_inbox"
    description: str = (
        "读取当前角色收件箱中未读消息。调用后消息会被原子地标记为 in_progress，"
        "返回未读消息快照 JSON。每次被 cron 唤醒（wake_reason=new_mail/heartbeat）后应先调用此工具。"
    )
    args_schema: type[BaseModel] = ReadInboxInput

    _workspace_root: Path = PrivateAttr()
    _role: str = PrivateAttr()

    def __init__(self, *, workspace_root: Path, role: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._workspace_root = workspace_root
        self._role = role

    def _run(self, project_id: str, **_: Any) -> str:
        if not _PROJECT_ID_RE.match(project_id):
            return json.dumps({"errcode": 1, "errmsg": f"invalid project_id: {project_id!r}"}, ensure_ascii=False)
        mailbox_dir = _project_root(self._workspace_root, project_id) / "mailboxes"
        try:
            snapshot = mailbox.read_inbox(mailbox_dir, role=self._role)
        except FileNotFoundError as exc:
            return json.dumps({"errcode": 1, "errmsg": str(exc)}, ensure_ascii=False)
        return json.dumps(
            {"errcode": 0, "role": self._role, "count": len(snapshot), "messages": snapshot},
            ensure_ascii=False,
        )


# ── MarkDoneTool ────────────────────────────────────────────────────────────


class MarkDoneInput(BaseModel):
    project_id: str = Field(..., description="项目 ID")
    msg_id: str = Field(..., description="要标记为 done 的消息 id (msg-xxxxxxxx)")


class MarkDoneTool(BaseTool):
    """把一条 in_progress 消息标记为 done。"""

    name: str = "mark_done"
    description: str = (
        "把收件箱中一条 in_progress 消息标记为 done。"
        "通常在处理完一条邮件（并已 send_mail 发出回执/分派/通知）后调用。"
        "拒绝对 unread/done 状态的消息执行。"
    )
    args_schema: type[BaseModel] = MarkDoneInput

    _workspace_root: Path = PrivateAttr()
    _role: str = PrivateAttr()

    def __init__(self, *, workspace_root: Path, role: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._workspace_root = workspace_root
        self._role = role

    def _run(self, project_id: str, msg_id: str, **_: Any) -> str:
        if not _PROJECT_ID_RE.match(project_id):
            return json.dumps({"errcode": 1, "errmsg": f"invalid project_id: {project_id!r}"}, ensure_ascii=False)
        mailbox_dir = _project_root(self._workspace_root, project_id) / "mailboxes"
        try:
            mailbox.mark_done(mailbox_dir, role=self._role, msg_id=msg_id)
            return json.dumps({"errcode": 0, "msg_id": msg_id, "status": "done"}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"errcode": 1, "errmsg": str(exc)}, ensure_ascii=False)


# ── CreateProjectTool (Manager only) ────────────────────────────────────────


class CreateProjectInput(BaseModel):
    project_id: str = Field(..., description="项目 ID：小写字母开头，仅允许 [a-z0-9_-]")
    project_name: str = Field(..., description="项目名")
    needs_content: str = Field(..., description="需求文档正文（写入 needs/requirements.md）")


class CreateProjectTool(BaseTool):
    """创建一个新项目：完整目录树 + 初始化邮箱 + events.jsonl + 首条事件."""

    name: str = "create_project"
    description: str = (
        "Manager 专用：创建新项目完整目录树（needs/design/tech/code/qa/reviews/mailboxes/logs），"
        "初始化 4 个邮箱、空 events.jsonl，写入 needs/requirements.md，追加 project_created 事件。"
        "幂等：同 project_id 重复调用只会补齐缺失部分。"
    )
    args_schema: type[BaseModel] = CreateProjectInput

    _workspace_root: Path = PrivateAttr()

    def __init__(self, *, workspace_root: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._workspace_root = workspace_root

    def _run(self, project_id: str, project_name: str, needs_content: str, **_: Any) -> str:
        if not _PROJECT_ID_RE.match(project_id):
            return json.dumps({"errcode": 1, "errmsg": f"invalid project_id: {project_id!r}"}, ensure_ascii=False)
        try:
            workspace.init_project_tree(self._workspace_root, project_id=project_id)
            # 写 needs/requirements.md（走 write_shared 权限校验 — manager 是 needs/ owner）
            workspace.write_shared(
                self._workspace_root,
                project_id=project_id,
                role="manager",
                rel_path="needs/requirements.md",
                content=needs_content,
            )
            # 追加 project_created 事件
            events_path = _project_root(self._workspace_root, project_id) / "events.jsonl"
            seq = event_log.append_event(
                events_path,
                action="project_created",
                payload={"project_id": project_id, "project_name": project_name},
            )
            return json.dumps(
                {"errcode": 0, "project_id": project_id, "event_seq": seq}, ensure_ascii=False
            )
        except Exception as exc:
            logger.exception("create_project failed")
            return json.dumps({"errcode": 1, "errmsg": str(exc)}, ensure_ascii=False)


# ── AppendEventTool (Manager only) ──────────────────────────────────────────


class AppendEventInput(BaseModel):
    project_id: str = Field(..., description="项目 ID")
    action: str = Field(..., description="事件类型（附录 A.3 枚举）")
    payload: dict = Field(..., description="事件 payload（结构化 dict）")


class AppendEventTool(BaseTool):
    """向 events.jsonl 追加一条事件（仅 Manager）."""

    name: str = "append_event"
    description: str = (
        "Manager 专用：向项目 events.jsonl 追加一条事件。"
        "常见 action：project_created / assigned / task_done_received / review_requested / "
        "checkpoint_requested / delivered / retro_triggered / retro_approved_by_manager 等（见附录 A）。"
    )
    args_schema: type[BaseModel] = AppendEventInput

    _workspace_root: Path = PrivateAttr()

    def __init__(self, *, workspace_root: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._workspace_root = workspace_root

    def _run(self, project_id: str, action: str, payload: dict, **_: Any) -> str:
        if not _PROJECT_ID_RE.match(project_id):
            return json.dumps({"errcode": 1, "errmsg": f"invalid project_id: {project_id!r}"}, ensure_ascii=False)
        events_path = _project_root(self._workspace_root, project_id) / "events.jsonl"
        try:
            seq = event_log.append_event(events_path, action=action, payload=payload)
            return json.dumps({"errcode": 0, "seq": seq}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"errcode": 1, "errmsg": str(exc)}, ensure_ascii=False)


# ── SendToHumanTool (Manager only) ──────────────────────────────────────────


class SendToHumanInput(BaseModel):
    routing_key: str = Field(..., description="飞书 routing_key，如 p2p:{open_id}")
    message: str = Field(..., description="发送给人类的 Markdown 文本")
    kind: str = Field(
        "info",
        description="info / checkpoint_request / proposal_review / delivery / evolution_report / error_alert",
    )
    project_id: str = Field("", description="可选关联项目 ID")
    checkpoint_id: str = Field("", description="若 kind=checkpoint_request 必填")


_VALID_KINDS = {
    "info",
    "checkpoint_request",
    "proposal_review",
    "delivery",
    "evolution_report",
    "error_alert",
}
_KIND_TO_EVENT = {
    "info": "info_sent",
    "checkpoint_request": "checkpoint_request_sent",
    "proposal_review": "proposal_review_sent",
    "delivery": "delivery_sent",
    "evolution_report": "evolution_report_sent",
    "error_alert": "error_alert_sent",
}


class SendToHumanTool(BaseTool):
    """Manager 专用：单一接口出站到飞书 + L1 联动事件."""

    name: str = "send_to_human"
    description: str = (
        "Manager 专用：把一条消息发给人类（通过飞书）。"
        "kind 决定事件类型（info/checkpoint_request/proposal_review/delivery/evolution_report/error_alert）。"
        "checkpoint_request 类型必须带 checkpoint_id；其他 kind 可选 project_id。"
        "调用后自动写一条事件到 events.jsonl（若带 project_id）。"
    )
    args_schema: type[BaseModel] = SendToHumanInput

    _workspace_root: Path = PrivateAttr()
    _sender: SenderProtocol | None = PrivateAttr(default=None)

    def __init__(
        self,
        *,
        workspace_root: Path,
        sender: SenderProtocol | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._workspace_root = workspace_root
        self._sender = sender

    def _run(
        self,
        routing_key: str,
        message: str,
        kind: str = "info",
        project_id: str = "",
        checkpoint_id: str = "",
        **_: Any,
    ) -> str:
        if kind not in _VALID_KINDS:
            return json.dumps({"errcode": 1, "errmsg": f"invalid kind: {kind!r}"}, ensure_ascii=False)
        if kind == "checkpoint_request" and not checkpoint_id:
            return json.dumps(
                {"errcode": 1, "errmsg": "checkpoint_request requires checkpoint_id"},
                ensure_ascii=False,
            )
        # 发消息
        # 💡 修复 C1：改用同步 sender 封装避免 fut.result 阻塞事件循环导致死锁
        if self._sender is None:
            logger.warning("SendToHumanTool: sender is None; skip feishu send (test mode)")
        else:
            try:
                import asyncio
                import threading

                coro = self._sender.send(routing_key, message, root_id="")
                # 在独立线程跑自己的 event loop，避免和主 loop 互相等待
                result_err: list[BaseException] = []

                def _run_in_thread() -> None:
                    try:
                        asyncio.run(coro)
                    except BaseException as e:  # noqa: BLE001
                        result_err.append(e)

                t = threading.Thread(target=_run_in_thread, daemon=True)
                t.start()
                t.join(timeout=15)
                if t.is_alive():
                    logger.warning("send_to_human: feishu send timed out after 15s, continuing anyway")
                elif result_err:
                    logger.warning("send_to_human: feishu send raised %s; continuing anyway", result_err[0])
            except Exception as exc:
                logger.exception("send_to_human: feishu send failed")
                return json.dumps({"errcode": 1, "errmsg": str(exc)}, ensure_ascii=False)
        # 写 event（若带 project_id）
        if project_id and _PROJECT_ID_RE.match(project_id):
            events_path = _project_root(self._workspace_root, project_id) / "events.jsonl"
            try:
                payload: dict[str, Any] = {"routing_key": routing_key, "kind": kind}
                if checkpoint_id:
                    payload["checkpoint_id"] = checkpoint_id
                event_log.append_event(
                    events_path,
                    action=_KIND_TO_EVENT[kind],
                    payload=payload,
                )
            except Exception:
                logger.warning("send_to_human: append_event failed", exc_info=True)
        return json.dumps(
            {"errcode": 0, "routing_key": routing_key, "kind": kind, "checkpoint_id": checkpoint_id},
            ensure_ascii=False,
        )


# ── ReadSharedTool / WriteSharedTool ────────────────────────────────────────


class ReadSharedInput(BaseModel):
    project_id: str = Field(..., description="项目 ID")
    rel_path: str = Field(..., description="相对项目目录的路径，如 design/product_spec.md")


class ReadSharedTool(BaseTool):
    """读取项目共享区文件（无 ACL，仅路径穿越防护）."""

    name: str = "read_shared"
    description: str = (
        "读取项目共享区文件内容。rel_path 相对 shared/projects/{project_id}/ 根，"
        "禁止 `..` 路径穿越。常用：needs/requirements.md, design/product_spec.md, tech/tech_design.md 等。"
    )
    args_schema: type[BaseModel] = ReadSharedInput

    _workspace_root: Path = PrivateAttr()
    _role: str = PrivateAttr()

    def __init__(self, *, workspace_root: Path, role: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._workspace_root = workspace_root
        self._role = role

    def _run(self, project_id: str, rel_path: str, **_: Any) -> str:
        if not _PROJECT_ID_RE.match(project_id):
            return json.dumps({"errcode": 1, "errmsg": f"invalid project_id: {project_id!r}"}, ensure_ascii=False)
        try:
            content = workspace.read_shared(
                self._workspace_root, project_id=project_id, role=self._role, rel_path=rel_path
            )
            return json.dumps(
                {"errcode": 0, "rel_path": rel_path, "content": content}, ensure_ascii=False
            )
        except FileNotFoundError:
            return json.dumps({"errcode": 1, "errmsg": f"not found: {rel_path}"}, ensure_ascii=False)
        except PermissionError as exc:
            return json.dumps({"errcode": 1, "errmsg": f"permission: {exc}"}, ensure_ascii=False)


class WriteSharedInput(BaseModel):
    project_id: str = Field(..., description="项目 ID")
    rel_path: str = Field(..., description="相对路径，owner 前缀受限：needs=manager, design=pm, tech/code=rd, qa=qa")
    content: str = Field(..., description="文件正文")


class WriteSharedTool(BaseTool):
    """写项目共享区文件（owner 前缀校验）."""

    name: str = "write_shared"
    description: str = (
        "写项目共享区文件。Owner 权限：needs/(manager) / design/(pm) / tech/+code/(rd) / qa/(qa) / "
        "reviews/{stage}/{reviewer}_{topic}.md (reviewer==自己)。"
        "mailboxes/ events.jsonl 必须走专用 Tool。"
    )
    args_schema: type[BaseModel] = WriteSharedInput

    _workspace_root: Path = PrivateAttr()
    _role: str = PrivateAttr()

    def __init__(self, *, workspace_root: Path, role: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._workspace_root = workspace_root
        self._role = role

    def _run(self, project_id: str, rel_path: str, content: str, **_: Any) -> str:
        if not _PROJECT_ID_RE.match(project_id):
            return json.dumps({"errcode": 1, "errmsg": f"invalid project_id: {project_id!r}"}, ensure_ascii=False)
        try:
            workspace.write_shared(
                self._workspace_root,
                project_id=project_id,
                role=self._role,
                rel_path=rel_path,
                content=content,
            )
            return json.dumps({"errcode": 0, "rel_path": rel_path}, ensure_ascii=False)
        except PermissionError as exc:
            return json.dumps({"errcode": 1, "errmsg": f"permission: {exc}"}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"errcode": 1, "errmsg": str(exc)}, ensure_ascii=False)


__all__ = [
    "SendMailTool",
    "ReadInboxTool",
    "MarkDoneTool",
    "CreateProjectTool",
    "AppendEventTool",
    "SendToHumanTool",
    "ReadSharedTool",
    "WriteSharedTool",
]