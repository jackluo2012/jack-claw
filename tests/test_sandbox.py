"""
Sandbox 模块测试
"""

import pytest
import asyncio
from pathlib import Path

from jackclaw.sandbox.client import SandboxClient


def run_async(coro):
    """同步运行 async 函数"""
    return asyncio.run(coro)


class TestSandboxClient:
    @pytest.fixture
    def client(self, tmp_path):
        return SandboxClient(workspace_dir=tmp_path, timeout=5.0)

    def test_init(self, client, tmp_path):
        assert client._workspace_dir == tmp_path
        assert client._timeout == 5.0

    def test_execute_python_success(self, client, tmp_path):
        result = run_async(client.execute_python("print('hello')", cwd=tmp_path))
        assert result["success"] is True
        assert result["returncode"] == 0
        assert "hello" in result["stdout"]

    def test_execute_python_syntax_error(self, client, tmp_path):
        result = run_async(client.execute_python("print(undefined_var)", cwd=tmp_path))
        assert result["success"] is False
        assert "NameError" in result["stderr"] or "Error" in result["stderr"]

    def test_execute_python_timeout(self):
        # 超时时间设为 0.1 秒，sleep 1 秒会超时
        client_short = SandboxClient(workspace_dir=Path("/tmp"), timeout=0.1)
        result = run_async(client_short.execute_python("import time; time.sleep(10)"))
        assert result["success"] is False
        assert "Timeout" in result.get("error", "")

    def test_execute_bash_success(self, client, tmp_path):
        result = run_async(client.execute_bash("echo hello", cwd=tmp_path))
        assert result["success"] is True
        assert result["returncode"] == 0

    def test_execute_bash_failure(self, client, tmp_path):
        result = run_async(client.execute_bash("exit 1", cwd=tmp_path))
        assert result["success"] is False
        assert result["returncode"] == 1

    def test_read_file(self, client, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        content = run_async(client.read_file(test_file))
        assert content == "hello world"

    def test_read_file_not_found(self, client, tmp_path):
        content = run_async(client.read_file(tmp_path / "nonexistent.txt"))
        assert content == ""

    def test_write_file(self, client, tmp_path):
        test_file = tmp_path / "output.txt"
        result = run_async(client.write_file(test_file, "test content"))
        assert result is True
        assert test_file.read_text() == "test content"

    def test_write_file_nested(self, client, tmp_path):
        test_file = tmp_path / "nested" / "dir" / "file.txt"
        result = run_async(client.write_file(test_file, "nested content"))
        assert result is True
        assert test_file.read_text() == "nested content"