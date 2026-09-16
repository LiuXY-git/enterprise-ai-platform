import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

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

    logger = logging.getLogger(LOGGER_NAME)

    if logger.handlers:
        return

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
