"""
沙盒客户端

Phase 4: 本地执行
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SandboxClient:
    """沙盒客户端"""

    def __init__(self, workspace_dir: Path, timeout: float = 60.0):
        self._workspace_dir = workspace_dir
        self._timeout = timeout

    async def execute_python(self, script: str, cwd: Path | None = None) -> dict[str, Any]:
        """执行 Python 脚本"""
        work_dir = cwd or self._workspace_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        script_path = work_dir / "_sandbox_script.py"
        script_path.write_text(script, encoding="utf-8")
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if script_path.exists():
                script_path.unlink()

    async def execute_bash(self, command: str, cwd: Path | None = None) -> dict[str, Any]:
        """执行 Bash 命令"""
        work_dir = cwd or self._workspace_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        try:
            proc = await asyncio.create_subprocess_shell(
                command, cwd=str(work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def read_file(self, path: Path) -> str:
        """读取文件"""
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    async def write_file(self, path: Path, content: str) -> bool:
        """写入文件"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False
