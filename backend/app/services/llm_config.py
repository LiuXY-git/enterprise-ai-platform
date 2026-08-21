import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


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
    api_key: str
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
        raise RuntimeError(f"不支持的 LLM_PROVIDER：{provider}；可选值：{supported}")

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

    return LLMConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
