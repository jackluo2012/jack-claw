"""
定时任务服务
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from jackclaw.cron.models import CronJob, ScheduleKind
from jackclaw.models import InboundMessage

logger = logging.getLogger(__name__)

DispatchFn = Callable[[InboundMessage], None]


class CronService:
    """定时任务服务"""

    def __init__(self, data_dir: Path, dispatch_fn: DispatchFn):
        self._data_dir = data_dir
        self._cron_dir = data_dir / "cron"
        self._cron_dir.mkdir(parents=True, exist_ok=True)
        self._tasks_path = self._cron_dir / "tasks.json"
        self._dispatch_fn = dispatch_fn
        self._jobs: dict[str, CronJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False

    def _now_ms(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    def _load_jobs(self) -> None:
        if not self._tasks_path.exists():
            return
        try:
            data = json.loads(self._tasks_path.read_text(encoding="utf-8"))
            for job_data in data.get("jobs", []):
                job = CronJob.from_dict(job_data)
                self._jobs[job.id] = job
        except Exception:
            pass

    def _save_jobs(self) -> None:
        data = {"jobs": [job.to_dict() for job in self._jobs.values()]}
        self._tasks_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def start(self) -> None:
        self._load_jobs()
        self._running = True
        for job in self._jobs.values():
            if job.enabled:
                self._schedule_job(job)
        logger.info("CronService started, %d jobs scheduled", len(self._tasks))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    def add_job(self, job: CronJob) -> None:
        self._jobs[job.id] = job
        self._save_jobs()
        if self._running and job.enabled:
            self._schedule_job(job)
        logger.info("Added cron job: %s", job.id)

    def remove_job(self, job_id: str) -> None:
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save_jobs()
        if job_id in self._tasks:
            self._tasks[job_id].cancel()
            del self._tasks[job_id]

    def list_jobs(self) -> list[CronJob]:
        return list(self._jobs.values())

    def _schedule_job(self, job: CronJob) -> None:
        if job.id in self._tasks:
            self._tasks[job.id].cancel()
        self._tasks[job.id] = asyncio.create_task(self._run_job_loop(job), name=f"cron-{job.id}")

    async def _run_job_loop(self, job: CronJob) -> None:
        while self._running and job.enabled:
            try:
                delay_ms = self._calc_delay(job)
                if delay_ms < 0:
                    job.enabled = False
                    self._save_jobs()
                    break
                await asyncio.sleep(delay_ms / 1000)
                await self._execute_job(job)
                job.last_run_at_ms = self._now_ms()
                if job.schedule.kind == ScheduleKind.AT:
                    job.enabled = False
                self._save_jobs()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Cron job error: %s", job.id)
                await asyncio.sleep(60)

    async def _execute_job(self, job: CronJob) -> None:
        logger.info("Executing cron job: %s", job.id)
        inbound = InboundMessage(
            routing_key=job.routing_key,
            content=job.content,
            msg_id=f"cron_{job.id}_{self._now_ms()}",
            root_id="",
            sender_id="cron",
            ts=self._now_ms(),
            is_cron=True,
        )
        try:
            await self._dispatch_fn(inbound)
        except Exception:
            logger.exception("Failed to dispatch cron job: %s", job.id)

    def _calc_delay(self, job: CronJob) -> int:
        now_ms = self._now_ms()
        schedule = job.schedule
        if schedule.kind == ScheduleKind.AT:
            from datetime import datetime
            at_dt = datetime.fromisoformat(schedule.at.replace("Z", "+00:00"))
            at_ms = int(at_dt.timestamp() * 1000)
            return at_ms - now_ms
        elif schedule.kind == ScheduleKind.EVERY:
            if job.last_run_at_ms == 0:
                anchor_ms = schedule.anchor_ms or now_ms
                elapsed = (now_ms - anchor_ms) % schedule.every_ms
                return schedule.every_ms - elapsed if elapsed > 0 else 0
            else:
                return schedule.every_ms
        elif schedule.kind == ScheduleKind.CRON:
            try:
                from croniter import croniter
                import zoneinfo
                tz = zoneinfo.ZoneInfo(schedule.tz)
                now = datetime.now(tz)
                cron = croniter(schedule.expr, now)
                next_dt = cron.get_next(datetime)
                next_ms = int(next_dt.timestamp() * 1000)
                return next_ms - now_ms
            except Exception:
                return -1
        return -1
