"""Central configuration; importing this module does not read .env or validate keys."""

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from dotenv import load_dotenv

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load_environment(env_file: Path | None = None) -> None:
    """Load once at an entry point; existing process values (even empty) win.

    The optional default .env may be absent. An explicitly selected file must
    exist. Interpolation is disabled: configuration values are literal strings.
    A changed .env requires a fresh process, not another call to this function.
    """
    path = DEFAULT_ENV_FILE if env_file is None else env_file
    try:
        if not path.exists() and env_file is None:
            return
        if not path.is_file():
            raise RuntimeError("配置环境文件不存在或不是普通文件")
        load_dotenv(path, override=False, interpolate=False, encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise RuntimeError("无法读取配置环境文件") from None


def _validate_base_url(value: str, name: str) -> None:
    """Reject credentials/query strings without reflecting user-supplied URLs."""
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and "?" not in value
            and "#" not in value
            and not any(char.isspace() or ord(char) < 32 for char in value)
            and "\\" not in value
        )
        # Accessing port also validates its syntax and range.
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise RuntimeError(
            f"{name} 必须是 HTTP(S) 地址，且不能包含凭据、查询参数或片段",
        ) from None


@dataclass(frozen=True)
class ProviderDefinition:
    api_key_env: str
    base_url_env: str
    model_env: str
    default_base_url: str
    default_model: str


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    api_key: str = field(repr=False)
    base_url: str
    model: str


PROVIDER_DEFINITIONS = {
    "deepseek": ProviderDefinition(
        api_key_env="DEEPSEEK_API_KEY",
        base_url_env="DEEPSEEK_BASE_URL",
        model_env="DEEPSEEK_MODEL",
        default_base_url="https://api.deepseek.com",
        default_model="deepseek-v4-flash",
    ),
    "qwen": ProviderDefinition(
        api_key_env="DASHSCOPE_API_KEY",
        base_url_env="QWEN_BASE_URL",
        model_env="QWEN_MODEL",
        default_base_url=("https://dashscope.aliyuncs.com/compatible-mode/v1"),
        default_model="qwen3.7-plus",
    ),
}


def get_llm_config() -> LLMConfig:
    provider = (
        os.getenv(
            "LLM_PROVIDER",
            "deepseek",
        )
        .strip()
        .lower()
    )

    definition = PROVIDER_DEFINITIONS.get(provider)

    if definition is None:
        supported = ", ".join(
            sorted(PROVIDER_DEFINITIONS),
        )
        raise RuntimeError(f"不支持的 LLM_PROVIDER；可选值：{supported}")

    api_key = os.getenv(
        definition.api_key_env,
        "",
    ).strip()
    base_url = os.getenv(
        definition.base_url_env,
        definition.default_base_url,
    ).strip()
    model = os.getenv(
        definition.model_env,
        definition.default_model,
    ).strip()

    if not api_key:
        raise RuntimeError(f"未配置 {definition.api_key_env}")

    if not base_url:
        raise RuntimeError(f"未配置 {definition.base_url_env}")

    if not model:
        raise RuntimeError(f"未配置 {definition.model_env}")

    _validate_base_url(base_url, definition.base_url_env)

    return LLMConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )


@dataclass(frozen=True)
class DifyWorkflowConfig:
    api_key: str = field(repr=False)
    base_url: str
    timeout_seconds: float


def get_dify_workflow_config() -> DifyWorkflowConfig:
    api_key = os.getenv(
        "DIFY_WORKFLOW_API_KEY",
        "",
    ).strip()
    base_url = os.getenv(
        "DIFY_API_BASE_URL",
        "http://localhost/v1",
    ).strip()
    timeout_value = os.getenv(
        "DIFY_WORKFLOW_TIMEOUT_SECONDS",
        "120",
    ).strip()

    if not api_key:
        raise RuntimeError("未配置 DIFY_WORKFLOW_API_KEY")

    if not base_url:
        raise RuntimeError("未配置 DIFY_API_BASE_URL")

    _validate_base_url(base_url, "DIFY_API_BASE_URL")

    try:
        timeout_seconds = float(timeout_value)
    except ValueError:
        raise RuntimeError(
            "DIFY_WORKFLOW_TIMEOUT_SECONDS 必须是数字",
        ) from None

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise RuntimeError(
            "DIFY_WORKFLOW_TIMEOUT_SECONDS 必须是有限正数",
        )

    return DifyWorkflowConfig(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        timeout_seconds=timeout_seconds,
    )


@dataclass(frozen=True)
class ExternalKnowledgeConfig:
    api_key: str = field(repr=False)
    knowledge_id: str


def get_external_knowledge_config() -> ExternalKnowledgeConfig:
    api_key = os.getenv(
        "DIFY_EXTERNAL_KNOWLEDGE_API_KEY",
        "",
    ).strip()
    knowledge_id = os.getenv(
        "DIFY_EXTERNAL_KNOWLEDGE_ID",
        "enterprise-knowledge-hub",
    ).strip()

    if not api_key:
        raise RuntimeError(
            "未配置 DIFY_EXTERNAL_KNOWLEDGE_API_KEY",
        )

    if not knowledge_id:
        raise RuntimeError(
            "未配置 DIFY_EXTERNAL_KNOWLEDGE_ID",
        )

    return ExternalKnowledgeConfig(
        api_key=api_key,
        knowledge_id=knowledge_id,
    )


@dataclass(frozen=True)
class FeishuConfig:
    app_id: str
    app_secret: str = field(repr=False)
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

    _validate_base_url(base_url, "FEISHU_API_BASE_URL")

    try:
        timeout_seconds = float(timeout_value)
    except ValueError:
        raise RuntimeError(
            "FEISHU_TIMEOUT_SECONDS 必须是数字",
        ) from None

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise RuntimeError(
            "FEISHU_TIMEOUT_SECONDS 必须是有限正数",
        )

    return FeishuConfig(
        app_id=app_id,
        app_secret=app_secret,
        base_url=base_url.rstrip("/"),
        timeout_seconds=timeout_seconds,
    )


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
    except ValueError:
        raise RuntimeError(
            "FEISHU_MAX_ATTEMPTS 必须是整数",
        ) from None

    if not 1 <= max_attempts <= 5:
        raise RuntimeError(
            "FEISHU_MAX_ATTEMPTS 必须在 1 到 5 之间",
        )

    try:
        retry_base_seconds = float(
            retry_base_seconds_value,
        )
    except ValueError:
        raise RuntimeError(
            "FEISHU_RETRY_BASE_SECONDS 必须是数字",
        ) from None

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
    except ValueError:
        raise RuntimeError("WECOM_AGENT_ID 必须是正整数") from None

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
    except ValueError:
        raise RuntimeError("WECOM_TIMEOUT_SECONDS 必须是有限正数") from None

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
