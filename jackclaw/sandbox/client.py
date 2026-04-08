"""
沙盒客户端 - Phase 4

提供安全的代码执行环境，支持：
- Python 脚本执行
- Bash 命令执行
- 文件读写

安全策略：
- 本地执行（Phase 4）
- 可配置超时
- 工作目录隔离

使用方式：
    sandbox = SandboxClient(workspace_dir=Path("./workspace"))
    
    # 执行 Python
    result = await sandbox.execute_python("print('Hello')")
    print(result["stdout"])  # "Hello"
    
    # 执行命令
    result = await sandbox.execute_bash("ls -la")
    
    # 文件操作
    await sandbox.write_file(Path("./test.txt"), "content")
    content = await sandbox.read_file(Path("./test.txt"))
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SandboxClient:
    """
    沙盒客户端
    
    提供本地代码执行能力。
    
    注意：Phase 4 为本地执行模式，后续可扩展为远程沙盒。
    """

    def __init__(self, workspace_dir: Path, timeout: float = 60.0):
        """
        初始化沙盒客户端
        
        Args:
            workspace_dir: 工作目录
            timeout: 执行超时时间（秒）
        """
        self._workspace_dir = workspace_dir
        self._timeout = timeout
        self._workspace_dir.mkdir(parents=True, exist_ok=True)

    async def execute_python(self, script: str, cwd: Path | None = None) -> dict[str, Any]:
        """
        执行 Python 脚本
        
        将脚本写入临时文件并执行。
        
        Args:
            script: Python 脚本代码
            cwd: 工作目录（默认使用 workspace_dir）
            
        Returns:
            执行结果：
            - success: 是否成功
            - returncode: 退出码
            - stdout: 标准输出
            - stderr: 标准错误
            - error: 错误信息（如果有）
        """
        work_dir = cwd or self._workspace_dir
        work_dir.mkdir(parents=True, exist_ok=True)

        # 写入临时脚本
        script_path = work_dir / "_sandbox_script.py"
        script_path.write_text(script, encoding="utf-8")

        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(work_dir),
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout,
            )

            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Timeout after {self._timeout}s",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

        finally:
            # 清理临时文件
            if script_path.exists():
                script_path.unlink()

    async def execute_bash(self, command: str, cwd: Path | None = None) -> dict[str, Any]:
        """
        执行 Bash 命令
        
        Args:
            command: Bash 命令
            cwd: 工作目录
            
        Returns:
            执行结果
        """
        work_dir = cwd or self._workspace_dir
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout,
            )

            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Timeout after {self._timeout}s",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def read_file(self, path: Path) -> str:
        """
        读取文件
        
        Args:
            path: 文件路径
            
        Returns:
            文件内容，失败返回空字符串
        """
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            logger.exception("Failed to read file: %s", path)
            return ""

    async def write_file(self, path: Path, content: str) -> bool:
        """
        写入文件
        
        Args:
            path: 文件路径
            content: 文件内容
            
        Returns:
            是否成功
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return True
        except Exception:
            logger.exception("Failed to write file: %s", path)
            return False
