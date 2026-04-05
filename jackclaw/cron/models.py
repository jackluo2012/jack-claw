"""
定时任务数据模型
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ScheduleKind(str, Enum):
    AT = "at"
    EVERY = "every"
    CRON = "cron"


@dataclass
class Schedule:
    """调度配置"""
    kind: ScheduleKind
    at: str = ""
    every_ms: int = 0
    anchor_ms: int = 0
    expr: str = ""
    tz: str = "Asia/Shanghai"

    def to_dict(self) -> dict:
        data = {"kind": self.kind.value}
        if self.kind == ScheduleKind.AT:
            data["at"] = self.at
        elif self.kind == ScheduleKind.EVERY:
            data["every_ms"] = self.every_ms
            if self.anchor_ms:
                data["anchor_ms"] = self.anchor_ms
        elif self.kind == ScheduleKind.CRON:
            data["expr"] = self.expr
            data["tz"] = self.tz
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Schedule":
        return cls(
            kind=ScheduleKind(data["kind"]),
            at=data.get("at", ""),
            every_ms=data.get("every_ms", 0),
            anchor_ms=data.get("anchor_ms", 0),
            expr=data.get("expr", ""),
            tz=data.get("tz", "Asia/Shanghai"),
        )


@dataclass
class CronJob:
    """定时任务"""
    id: str
    name: str
    schedule: Schedule
    routing_key: str
    content: str
    enabled: bool = True
    created_at: int = 0
    next_run_at_ms: int = 0
    last_run_at_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "schedule": self.schedule.to_dict(),
            "routing_key": self.routing_key,
            "content": self.content,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "next_run_at_ms": self.next_run_at_ms,
            "last_run_at_ms": self.last_run_at_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CronJob":
        return cls(
            id=data["id"],
            name=data["name"],
            schedule=Schedule.from_dict(data["schedule"]),
            routing_key=data["routing_key"],
            content=data["content"],
            enabled=data.get("enabled", True),
            created_at=data.get("created_at", 0),
            next_run_at_ms=data.get("next_run_at_ms", 0),
            last_run_at_ms=data.get("last_run_at_ms", 0),
            metadata=data.get("metadata", {}),
        )
