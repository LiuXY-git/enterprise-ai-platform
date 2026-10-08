"""Keep API environment-file selection out of automated test runs."""

import pytest


@pytest.fixture(autouse=True)
def isolated_environment_selection(monkeypatch):
    monkeypatch.delenv("EAP_ENV_FILE", raising=False)
