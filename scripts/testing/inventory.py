"""Record collection and execution so missing/skipped tests cannot pass silently."""

import json
import platform
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption("--eap-inventory", required=True)


def pytest_sessionstart(session):
    session.config._eap_executed = set()
    session.config._eap_collected = []


def pytest_collection_finish(session):
    session.config._eap_collected = [item.nodeid for item in session.items]


def pytest_runtest_protocol(item, nextitem):
    item.config._eap_executed.add(item.nodeid)


def pytest_sessionfinish(session, exitstatus):
    data = {
        "collected": session.config._eap_collected,
        "executed": sorted(session.config._eap_executed),
        "exit_code": int(exitstatus),
        "python_version": platform.python_version(),
        "pytest_version": pytest.__version__,
    }
    Path(session.config.getoption("--eap-inventory")).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
