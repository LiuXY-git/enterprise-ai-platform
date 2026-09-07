import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class FeishuConfig:
    app_id: str
    app_secret: str
    base_url: str
    timeout_seconds: float


def get_feishu_config() -> FeishuConfig:
    app_id = os.getenv(
        "FEISHU_APP_ID",
        "",
    ).strip()
    app_secret = os.getenv(
        "FEISHU_APP_SECRET",
        "",
    ).strip()
    base_url = os.getenv(
        "FEISHU_API_BASE_URL",
        "https://open.feishu.cn/open-apis",
    ).strip()
    timeout_value = os.getenv(
        "FEISHU_TIMEOUT_SECONDS",
        "10",
    ).strip()

    if not app_id:
        raise RuntimeError("未配置 FEISHU_APP_ID")

    if not app_secret:
        raise RuntimeError("未配置 FEISHU_APP_SECRET")

    if not base_url:
        raise RuntimeError("未配置 FEISHU_API_BASE_URL")

    try:
        timeout_seconds = float(timeout_value)
    except ValueError as exc:
        raise RuntimeError(
            "FEISHU_TIMEOUT_SECONDS 必须是数字",
        ) from exc

    if timeout_seconds <= 0:
        raise RuntimeError(
            "FEISHU_TIMEOUT_SECONDS 必须大于 0",
        )

    return FeishuConfig(
        app_id=app_id,
        app_secret=app_secret,
        base_url=base_url.rstrip("/"),
        timeout_seconds=timeout_seconds,
    )
