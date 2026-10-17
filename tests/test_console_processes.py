"""Run in the Linux worker image: timeout cleanup must include MCP descendants."""

import os
import subprocess
import sys
import time

import pytest

from backend.app.console.sales_worker import stop_group

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="Linux process-group proof requires the worker container",
)


def test_cleanup_kills_descendant_after_parent_exit(tmp_path):
    assert os.name == "posix", (
        "This process-group proof must run inside the Linux worker"
    )
    pidfile = tmp_path / "child.pid"
    code = "import subprocess,sys; from pathlib import Path; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); Path(sys.argv[1]).write_text(str(p.pid))"
    parent = subprocess.Popen(
        [sys.executable, "-c", code, str(pidfile)], start_new_session=True
    )
    child = None
    try:
        parent.wait(timeout=5)
        child = int(pidfile.read_text())
        os.kill(child, 0)
        stop_group(parent)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            stat = f"/proc/{child}/stat"
            if not os.path.exists(stat):
                return
            with open(stat) as stream:
                if stream.read().split()[2] == "Z":
                    return
            time.sleep(0.05)
        raise AssertionError("descendant still running")
    finally:
        stop_group(parent)
