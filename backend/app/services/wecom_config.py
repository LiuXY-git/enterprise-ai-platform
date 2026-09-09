import math
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://qyapi.weixin.qq.com"


@dataclass(frozen=True)
class WeComConfig:
    corp_id: str
    agent_id: int
    app_secret: str = field(repr=False)
    to_user: str
    base_url: str
    timeout_seconds: float


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(f"未配置 {name}")

    return value


def get_wecom_config() -> WeComConfig:
    corp_id = _required_env("WECOM_CORP_ID")
    agent_id_value = _required_env("WECOM_AGENT_ID")
    app_secret = _required_env("WECOM_APP_SECRET")
    to_user = _required_env("WECOM_TO_USER")

    # AgentID 在请求体中使用整数，而不是字符串。
    if not (agent_id_value.isascii() and agent_id_value.isdecimal()):
        raise RuntimeError("WECOM_AGENT_ID 必须是正整数")

    try:
        agent_id = int(agent_id_value)
    except ValueError as exc:
        raise RuntimeError("WECOM_AGENT_ID 必须是正整数") from exc

    if agent_id <= 0:
        raise RuntimeError("WECOM_AGENT_ID 必须是正整数")

    # Day 45 只允许向一个指定测试成员发送。
    if (
        to_user.lower() == "@all"
        or "|" in to_user
        or any(char.isspace() for char in to_user)
    ):
        raise RuntimeError("WECOM_TO_USER 必须是单个成员账号，不允许群发或空白字符")

    base_url = (
        os.getenv(
            "WECOM_API_BASE_URL",
            DEFAULT_BASE_URL,
        )
        .strip()
        .rstrip("/")
    )

    # 本项目暂不支持代理网关，避免把凭据发送到错误地址。
    # 测试使用 MockTransport，不需要修改真实 API 地址。
    if base_url != DEFAULT_BASE_URL:
        raise RuntimeError("WECOM_API_BASE_URL 必须是 https://qyapi.weixin.qq.com")

    timeout_value = os.getenv(
        "WECOM_TIMEOUT_SECONDS",
        "10",
    ).strip()

    try:
        timeout_seconds = float(timeout_value)
    except ValueError as exc:
        raise RuntimeError("WECOM_TIMEOUT_SECONDS 必须是有限正数") from exc

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise RuntimeError("WECOM_TIMEOUT_SECONDS 必须是有限正数")

    return WeComConfig(
        corp_id=corp_id,
        agent_id=agent_id,
        app_secret=app_secret,
        to_user=to_user,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
