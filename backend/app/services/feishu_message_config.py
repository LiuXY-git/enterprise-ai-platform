import math
import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class FeishuMessageConfig:
    receive_id_type: Literal["open_id", "chat_id"]
    receive_id: str
    max_attempts: int
    retry_base_seconds: float


def get_feishu_message_config() -> FeishuMessageConfig:
    receive_id_type_value = os.getenv(
        "FEISHU_RECEIVE_ID_TYPE",
        "chat_id",
    ).strip()
    receive_id = os.getenv(
        "FEISHU_RECEIVE_ID",
        "",
    ).strip()
    max_attempts_value = os.getenv(
        "FEISHU_MAX_ATTEMPTS",
        "3",
    ).strip()
    retry_base_seconds_value = os.getenv(
        "FEISHU_RETRY_BASE_SECONDS",
        "0.5",
    ).strip()

    # 接收者类型只支持员工 open_id 和会话 chat_id。
    receive_id_type: Literal["open_id", "chat_id"]

    if receive_id_type_value == "open_id":
        receive_id_type = "open_id"
    elif receive_id_type_value == "chat_id":
        receive_id_type = "chat_id"
    else:
        raise RuntimeError(
            "FEISHU_RECEIVE_ID_TYPE 必须是 open_id 或 chat_id",
        )

    if not receive_id:
        raise RuntimeError("未配置 FEISHU_RECEIVE_ID")

    expected_prefix = "ou_" if receive_id_type == "open_id" else "oc_"

    if not receive_id.startswith(expected_prefix) or len(receive_id) <= len(
        expected_prefix
    ):
        raise RuntimeError(
            f"FEISHU_RECEIVE_ID 必须是以 {expected_prefix} "
            f"开头的有效 {receive_id_type}",
        )

    # max_attempts 包含首次请求，例如 3 表示最多重试 2 次。
    try:
        max_attempts = int(max_attempts_value)
    except ValueError as exc:
        raise RuntimeError(
            "FEISHU_MAX_ATTEMPTS 必须是整数",
        ) from exc

    if not 1 <= max_attempts <= 5:
        raise RuntimeError(
            "FEISHU_MAX_ATTEMPTS 必须在 1 到 5 之间",
        )

    try:
        retry_base_seconds = float(
            retry_base_seconds_value,
        )
    except ValueError as exc:
        raise RuntimeError(
            "FEISHU_RETRY_BASE_SECONDS 必须是数字",
        ) from exc

    if not math.isfinite(retry_base_seconds) or retry_base_seconds < 0:
        raise RuntimeError(
            "FEISHU_RETRY_BASE_SECONDS 必须是大于等于 0 的有限数字",
        )

    return FeishuMessageConfig(
        receive_id_type=receive_id_type,
        receive_id=receive_id,
        max_attempts=max_attempts,
        retry_base_seconds=retry_base_seconds,
    )
