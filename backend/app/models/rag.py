from pydantic import BaseModel, Field


class RagQueryRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=500,
        description="需要从企业知识库中查询的问题。",
        examples=["当前项目版本是多少？"],
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="返回的相关文档片段数量，取值范围为 1 到 10。",
        examples=[3],
    )


class RagSearchResult(BaseModel):
    id: str = Field(
        description="文档片段在向量数据库中的唯一标识。",
        examples=["readme-chunk-13"],
    )
    text: str = Field(
        description="检索到的文档片段原文。",
        examples=["当前项目版本为 v1.0.0。"],
    )
    source: str = Field(
        description="文档片段所属的来源文件。",
        examples=["README.md"],
    )
    chunk_index: int = Field(
        description="文档片段在来源文件中的序号。",
        examples=[13],
    )
    distance: float = Field(
        description="向量距离，数值越小通常表示相关性越高。",
        examples=[0.82],
    )


class RagQueryResponse(BaseModel):
    question: str = Field(
        description="本次检索使用的问题。",
        examples=["当前项目版本是多少？"],
    )
    results: list[RagSearchResult] = Field(
        description="按照相关性排序的文档片段。",
    )


class RagSource(BaseModel):
    label: str = Field(
        description="回答中使用的来源引用标签。",
        examples=["[来源1]"],
    )
    id: str = Field(
        description="来源文档片段的唯一标识。",
        examples=["readme-chunk-13"],
    )
    source: str = Field(
        description="来源文件名称。",
        examples=["README.md"],
    )
    chunk_index: int = Field(
        description="文档片段在来源文件中的序号。",
        examples=[13],
    )
    text: str = Field(
        description="用于生成回答的来源文本。",
        examples=["当前项目版本为 v1.0.0。"],
    )
    distance: float = Field(
        description="来源文本与问题之间的向量距离。",
        examples=[0.82],
    )


class RagAnswerResponse(BaseModel):
    question: str = Field(
        description="用户提交的问题。",
        examples=["当前项目版本是多少？"],
    )
    answer: str = Field(
        description="根据知识库内容生成并包含来源引用的回答。",
        examples=["当前项目版本为 v1.0.0。[来源1]"],
    )
    sources: list[RagSource] = Field(
        description="生成回答时使用的来源列表。",
    )
