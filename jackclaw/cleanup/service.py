"""
文件清理服务
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class CleanupService:
    """文件清理服务"""

    def __init__(
        self,
        data_dir: Path,
        uploads_max_days: int = 7,
        outputs_max_days: int = 30,
    ):
        self._data_dir = data_dir
        self._uploads_max_days = uploads_max_days
        self._outputs_max_days = outputs_max_days

    def _now_ms(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    async def sweep(self) -> None:
        """执行清理"""
        logger.info("CleanupService: starting sweep")
        workspace_dir = self._data_dir / "workspace"
        if not workspace_dir.exists():
            return
        now_ms = self._now_ms()
        deleted_count = 0
        sessions_dir = workspace_dir / "sessions"
        if sessions_dir.exists():
            for session_dir in sessions_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                uploads_dir = session_dir / "uploads"
                if uploads_dir.exists():
                    count = await self._clean_dir(uploads_dir, now_ms, self._uploads_max_days)
                    deleted_count += count
                outputs_dir = session_dir / "outputs"
                if outputs_dir.exists():
                    count = await self._clean_dir(outputs_dir, now_ms, self._outputs_max_days)
                    deleted_count += count
        logger.info("CleanupService: deleted %d files", deleted_count)

    async def _clean_dir(self, dir_path: Path, now_ms: int, max_days: int) -> int:
        """清理目录中过期文件"""
        max_age_ms = max_days * 24 * 60 * 60 * 1000
        deleted_count = 0
        for file_path in dir_path.iterdir():
            if not file_path.is_file():
                continue
            try:
                mtime_ms = int(file_path.stat().st_mtime * 1000)
                if now_ms - mtime_ms > max_age_ms:
                    file_path.unlink()
                    deleted_count += 1
            except Exception:
                pass
        return deleted_count
