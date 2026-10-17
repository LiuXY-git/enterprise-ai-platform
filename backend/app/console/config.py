"""Server-owned limits shared by the console API and its worker."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConsoleConfig:
    data_dir: Path
    queue_limit: int = 32
    timeout_seconds: float = 10
    agent_timeout_seconds: float = 60
    heartbeat_seconds: float = 1
    lease_seconds: float = 15
    poll_seconds: float = 0.25

    def __post_init__(self):
        if not 1 <= self.queue_limit <= 1000:
            raise ValueError("invalid_console_queue_limit")
        if not 0 < self.timeout_seconds <= 3600:
            raise ValueError("invalid_console_timeout")
        if not 1 <= self.agent_timeout_seconds <= 300:
            raise ValueError("invalid_agent_timeout")
        if not 0 < self.heartbeat_seconds < self.lease_seconds / 2:
            raise ValueError("invalid_console_heartbeat")
        if not 0 < self.poll_seconds <= self.heartbeat_seconds:
            raise ValueError("invalid_console_poll_interval")

    @property
    def database(self):
        return self.data_dir / "jobs.sqlite"

    @classmethod
    def from_environment(cls):
        default = Path(__file__).resolve().parents[3] / "data" / "web-console"
        return cls(
            data_dir=Path(os.getenv("WEB_CONSOLE_DATA_DIR", str(default))).resolve(),
            queue_limit=int(os.getenv("WEB_CONSOLE_QUEUE_LIMIT", "32")),
            timeout_seconds=float(os.getenv("WEB_CONSOLE_TIMEOUT_SECONDS", "10")),
            agent_timeout_seconds=float(
                os.getenv("WEB_CONSOLE_AGENT_TIMEOUT_SECONDS", "60")
            ),
        )
