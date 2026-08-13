import logging
from pathlib import Path

LOGGER_NAME = "enterprise_ai_platform"

LOG_DIRECTORY = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE = LOG_DIRECTORY / "app.log"


def configure_logging() -> None:
    LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

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

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
