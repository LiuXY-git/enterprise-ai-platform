"""Select the API environment file once at application startup."""

import os
from pathlib import Path

from .. import settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def resolve_env_file(value: str, root: Path = PROJECT_ROOT) -> Path:
    if not value.strip():
        raise RuntimeError("环境文件路径不能为空")
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_environment() -> None:
    selected = os.environ.get("EAP_ENV_FILE")
    if selected is None:
        settings.load_environment()
    else:
        # A selected file replaces the default file; it is never layered over it.
        settings.load_environment(resolve_env_file(selected))
