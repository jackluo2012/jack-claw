"""
feishu_bridge.py — 飞书单一接口 + Checkpoint 跟踪 + 消息分类

对齐 DESIGN.md v1.5 §12：
- 唯一对外通道：Manager 的 send_to_human（出站）/ 飞书入站消息 → Manager
- CheckpointStore：跨 wake 持久化 pending checkpoints（`shared/feishu_bridge/pending.jsonl`）
- classify(text, callback_value)：新需求 / checkpoint 回复 / 澄清回答 / SOP 共创 / 兜底 need_discussion

特别强调：此模块是"工具"，不做业务决策。Manager 读入分类结果和 pending list，用 Skill 决定下一步。
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from filelock import FileLock

logger = logging.getLogger(__name__)
Category = Literal[
    "checkpoint_response",
    "new_requirement",
    "clarification_answer",
    "sop_cocreate",
    "need_discussion",
]

_NEW_REQ_KEYWORDS = {
    # 中文触发
    "帮我做", "做一个", "帮我写", "搭一个", "搭个", "实现", "开发一个", "建一个",
    "构建", "需求", "新项目", "新需求",
    # 英文
    "build", "create", "implement", "new project", "new feature",
}
_SOP_KEYWORDS = {"sop", "流程", "标准", "工作流", "规范", "workflow"}
_CLARIFICATION_KEYWORDS = {"答复", "回答", "澄清", "答案", "answer"}

@dataclass
class PendingCheckpoint:
    """一条待回应的 checkpoint（Manager 发了 checkpoint_request 等待人类回复）."""

    checkpoint_id: str
    routing_key: str
    project_id: str
    kind: str              # checkpoint_request / proposal_review / ...
    question: str          # 提问摘要
    created_at_ms: int

def _now_ms() -> int:
    return int(time.time() * 1000)

class CheckpointStore:
    """JSONL 文件持久化 pending checkpoints；FileLock 保护并发."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = FileLock(str(path) + ".lock")

    def _ensure(self) -> None:

        """
        确保文件路径存在的方法
        如果路径的父目录不存在，则创建所有必要的父目录
        如果目标文件不存在，则创建一个空文件
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)  # 创建父目录，包括所有必要的父级目录
        if not self._path.exists():
            self._path.write_text("")

    def _read_all(self) -> list[PendingCheckpoint]:
        # 确保资源已初始化
        self._ensure()
        # 用于存储已解析的检查点ID集合
        resolved_ids: set[str] = set()
        # 用于存储原始条目的列表
        raw_entries: list[dict] = []
        # 读取文件内容并逐行处理
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            # 跳过空行
            if not line:
                continue
            try:
                # 尝试解析JSON格式的行
                d = json.loads(line)
            except json.JSONDecodeError:
                # 如果解析失败则跳过该行
                continue
            # 检查是否为已解析的检查点，如果是则添加到resolved_ids集合
            if d.get("resolved_at_ms") and "checkpoint_id" in d and "routing_key" not in d:
                resolved_ids.add(d["checkpoint_id"])
                continue
            # 将有效条目添加到raw_entries列表
            raw_entries.append(d)

        # 用于存储最终的待处理检查点列表
        out: list[PendingCheckpoint] = []
        # 遍历原始条目，创建PendingCheckpoint对象
        for d in raw_entries:
            cid = d.get("checkpoint_id")
            # 如果检查点ID不存在或已在已解析集合中，则跳过
            if not cid or cid in resolved_ids:
                continue
            try:
                # 创建PendingCheckpoint对象并添加到结果列表
                out.append(
                    PendingCheckpoint(
                        checkpoint_id=cid,
                        routing_key=d["routing_key"],
                        project_id=d.get("project_id", ""),
                        kind=d.get("kind", "checkpoint_request"),
                        question=d.get("question", ""),
                        created_at_ms=int(d.get("created_at_ms", 0)),
                    )
                )
            except KeyError:
                # 如果缺少必要字段则跳过该条目
                continue
        return out

    def register(
        self,
        *,
        routing_key: str,
        project_id: str,
        kind: str,
        question: str,
        checkpoint_id: str | None = None,
    ) -> str:
        cid = checkpoint_id or f"ckpt-{uuid.uuid4().hex[:8]}"
        entry = {
            "checkpoint_id": cid,
            "routing_key": routing_key,
            "project_id": project_id,
            "kind": kind,
            "question": question,
            "created_at_ms": _now_ms(),
            "resolved_at_ms": None,
        }
        with self._lock:
            self._ensure()
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return cid

    def pending(self) -> list[PendingCheckpoint]:
        """
        获取所有待处理的检查点
        Returns:
            list[PendingCheckpoint]: 返回包含所有待处理检查点的列表
        """
        with self._lock:
            # 使用锁确保线程安全，读取所有待处理检查点
            return self._read_all()

    def pending_for_routing_key(self, routing_key: str) -> list[PendingCheckpoint]:
        with self._lock:
            return [c for c in self._read_all() if c.routing_key == routing_key]

    def resolve(self, checkpoint_id: str) -> bool:
        """标记 checkpoint 为 resolved（加 resolved_at_ms 行）.

        返回 False：checkpoint 不存在 或 已被 resolve（幂等）.
        """
        # 使用锁确保线程安全
        with self._lock:
            # 确保资源已初始化
            self._ensure()
            # 读取文件内容并按行分割
            existing = self._path.read_text(encoding="utf-8").splitlines()
            has_registered = False  # 标记是否有已注册的checkpoint
            already_resolved = False  # 标记是否已被resolve
            # 遍历文件中的每一行
            for line in existing:
                line = line.strip()  # 去除首尾空白字符
                if not line:  # 跳过空行
                    continue
                try:
                    # 解析JSON格式的行数据
                    d = json.loads(line)
                except json.JSONDecodeError:
                    # 如果解析失败则跳过该行
                    continue
                # 检查当前行是否匹配目标checkpoint_id
                if d.get("checkpoint_id") != checkpoint_id:
                    continue
                # 检查是否已被resolve
                if d.get("resolved_at_ms") and "routing_key" not in d:
                    already_resolved = True
                # 检查是否已注册
                elif "routing_key" in d:
                    has_registered = True
            # 如果checkpoint已被resolve或未注册，则返回False
            if already_resolved or not has_registered:
                return False
            # 追加 resolve marker
            with self._path.open("a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {"checkpoint_id": checkpoint_id, "resolved_at_ms": _now_ms()},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            return True


def _match_keywords(text: str, keywords: set[str]) -> bool:
    t = text.lower()
    return any(kw.lower() in t for kw in keywords)


def classify(
    text: str,
    *,
    callback_value: dict | None = None,
    pending_for_rk: list[PendingCheckpoint] | None = None,
) -> tuple[Category, str | None]:
    """分类一条人类输入。返回 (category, checkpoint_id)。"""
    pending_for_rk = pending_for_rk or []

    # 1. 飞书卡片 callback 最优先
    if callback_value and "checkpoint_id" in callback_value:
        return "checkpoint_response", callback_value["checkpoint_id"]

    stripped = (text or "").strip()
    if not stripped:
        return "need_discussion", None

    # 2. 文本匹配显式 checkpoint_id（格式 ckpt-xxxx）
    m = re.search(r"ckpt-[0-9a-f]{8}", stripped)
    if m and any(c.checkpoint_id == m.group(0) for c in pending_for_rk):
        return "checkpoint_response", m.group(0)

    # 3. 有 pending 但用户直接复述 question 的关键片段，算 checkpoint_response
    if pending_for_rk:
        # 最新那条 = created_at_ms 最大；平票时取 pending 列表末尾（文件 append 顺序）
        latest = pending_for_rk[-1]
        for c in reversed(pending_for_rk):
            if c.created_at_ms > latest.created_at_ms:
                latest = c
        # 兜底规则：有 pending 时默认把 "同意/批准/approve/reject/拒绝" 类直接绑到最新那条
        short = stripped.lower()
        decision_tokens = {"同意", "批准", "approve", "yes", "确认", "ok",
                           "拒绝", "不同意", "reject", "no"}
        if any(tok in short for tok in decision_tokens):
            return "checkpoint_response", latest.checkpoint_id

    # 4. 关键词分类
    if _match_keywords(stripped, _SOP_KEYWORDS):
        return "sop_cocreate", None
    if _match_keywords(stripped, _NEW_REQ_KEYWORDS):
        return "new_requirement", None
    if _match_keywords(stripped, _CLARIFICATION_KEYWORDS):
        return "clarification_answer", None

    return "need_discussion", None


def serialize_pending(pending: list[PendingCheckpoint]) -> list[dict]:
    return [asdict(p) for p in pending]


__all__ = [
    "Category",
    "CheckpointStore",
    "PendingCheckpoint",
    "classify",
    "serialize_pending",
]