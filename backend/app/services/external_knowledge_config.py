import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ExternalKnowledgeConfig:
    api_key: str
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
