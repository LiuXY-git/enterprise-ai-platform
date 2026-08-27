from typing import Any

from pydantic import BaseModel, Field


class RetrievalSetting(BaseModel):
    top_k: int = Field(
        ge=1,
        le=10,
        description="最多返回的知识片段数量。",
        examples=[3],
    )
    score_threshold: float = Field(
        ge=0.0,
        le=1.0,
        description="结果需要达到的最低相关性分数。",
        examples=[0.5],
    )


class ExternalKnowledgeRequest(BaseModel):
    knowledge_id: str = Field(
        min_length=1,
        max_length=100,
        description="Dify 中配置的外部知识库标识。",
        examples=["enterprise-knowledge-hub"],
    )
    query: str = Field(
        min_length=1,
        max_length=500,
        description="需要从知识库中检索的问题。",
        examples=["当前项目版本是多少？"],
    )
    retrieval_setting: RetrievalSetting
    metadata_condition: dict[str, Any] | None = Field(
        default=None,
        description="Dify 传入的可选元数据过滤条件。",
    )


class ExternalKnowledgeRecord(BaseModel):
    content: str = Field(
        description="检索到的文档片段内容。",
    )
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="文档片段与查询的相关性分数。",
    )
    title: str = Field(
        description="来源文档名称。",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="来源、片段序号等附加信息。",
    )


class ExternalKnowledgeResponse(BaseModel):
    records: list[ExternalKnowledgeRecord] = Field(
        description="返回给 Dify 的相关知识片段。",
    )
