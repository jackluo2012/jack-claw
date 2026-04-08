"""
Cron 模块测试
"""

import pytest
from jackclaw.cron.models import ScheduleKind, Schedule, CronJob


class TestSchedule:
    def test_schedule_at(self):
        schedule = Schedule(kind=ScheduleKind.AT, at="2024-01-15T09:00:00Z")
        data = schedule.to_dict()
        assert data["kind"] == "at"
        assert data["at"] == "2024-01-15T09:00:00Z"

    def test_schedule_from_dict_at(self):
        data = {"kind": "at", "at": "2024-01-15T09:00:00Z"}
        schedule = Schedule.from_dict(data)
        assert schedule.kind == ScheduleKind.AT
        assert schedule.at == "2024-01-15T09:00:00Z"

    def test_schedule_every(self):
        schedule = Schedule(kind=ScheduleKind.EVERY, every_ms=3600000, anchor_ms=1704067200000)
        data = schedule.to_dict()
        assert data["kind"] == "every"
        assert data["every_ms"] == 3600000
        assert data["anchor_ms"] == 1704067200000

    def test_schedule_cron(self):
        schedule = Schedule(kind=ScheduleKind.CRON, expr="0 9 * * 1-5", tz="Asia/Shanghai")
        data = schedule.to_dict()
        assert data["kind"] == "cron"
        assert data["expr"] == "0 9 * * 1-5"
        assert data["tz"] == "Asia/Shanghai"


class TestCronJob:
    def test_cron_job_to_dict(self):
        schedule = Schedule(kind=ScheduleKind.AT, at="2024-01-15T09:00:00Z")
        job = CronJob(
            id="test_job_1",
            name="测试任务",
            schedule=schedule,
            routing_key="p2p:ou_xxx",
            content="提醒内容",
        )
        data = job.to_dict()
        assert data["id"] == "test_job_1"
        assert data["name"] == "测试任务"
        assert data["routing_key"] == "p2p:ou_xxx"
        assert data["enabled"] is True

    def test_cron_job_from_dict(self):
        data = {
            "id": "test_job_2",
            "name": "测试任务2",
            "schedule": {"kind": "every", "every_ms": 3600000},
            "routing_key": "group:oc_xxx",
            "content": "内容",
            "enabled": False,
        }
        job = CronJob.from_dict(data)
        assert job.id == "test_job_2"
        assert job.schedule.kind == ScheduleKind.EVERY
        assert job.enabled is False
