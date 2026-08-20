from pydantic import BaseModel, Field


class RagQueryRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=500,
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
    )


class RagSearchResult(BaseModel):
    id: str
    text: str
    source: str
    chunk_index: int
    distance: float


class RagQueryResponse(BaseModel):
    question: str
    results: list[RagSearchResult]


class RagSource(BaseModel):
    label: str
    id: str
    source: str
    chunk_index: int
    text: str
    distance: float


class RagAnswerResponse(BaseModel):
    question: str
    answer: str
    sources: list[RagSource]
