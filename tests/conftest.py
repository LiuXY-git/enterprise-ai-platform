"""Keep configuration and lifecycle tests independent of developer secrets."""

import os

import pytest

from backend.app import settings


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch, tmp_path):
    prefixes = (
        "LLM_",
        "DEEPSEEK_",
        "DASHSCOPE_",
        "QWEN_",
        "DIFY_",
        "FEISHU_",
        "WECOM_",
    )
    # Also isolate keys added directly by dotenv, not only monkeypatch.setenv.
    monkeypatch.setattr(
        os,
        "environ",
        {
            name: value
            for name, value in os.environ.items()
            if not name.startswith(prefixes)
        },
    )
    monkeypatch.setattr(settings, "DEFAULT_ENV_FILE", tmp_path / "absent.env")
