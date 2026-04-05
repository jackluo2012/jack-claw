"""配置加载测试"""

import pytest
from pathlib import Path
from unittest.mock import patch

from jackclaw.config import load_config, _expand_env_vars


def test_expand_env_vars_string():
    with patch.dict("os.environ", {"TEST_VAR": "test_value"}):
        result = _expand_env_vars("${TEST_VAR}")
        assert result == "test_value"


def test_expand_env_vars_dict():
    with patch.dict("os.environ", {"APP_ID": "12345"}):
        result = _expand_env_vars({"feishu": {"app_id": "${APP_ID}"}})
        assert result["feishu"]["app_id"] == "12345"


def test_load_config_not_found():
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))
