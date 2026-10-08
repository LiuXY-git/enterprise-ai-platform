import logging
from pathlib import Path

from .observability import (
    JsonFormatter,
    SafeConsoleHandler,
    SafeRotatingFileHandler,
    configure_server_logging,
)
from .workflow_logging import configure_workflow_logging

LOGGER_NAME = "enterprise_ai_platform"

LOG_DIRECTORY = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE = LOG_DIRECTORY / "app.log"


def configure_logging() -> None:
    LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    configure_workflow_logging(LOG_DIRECTORY)

    formatter = JsonFormatter()
    configure_server_logging(formatter)
    logger = logging.getLogger(LOGGER_NAME)

    if logger.handlers:
        return

    logger.setLevel(logging.INFO)
    logger.propagate = False

    console_handler = SafeConsoleHandler()
    console_handler.setFormatter(formatter)

    file_handler = SafeRotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
