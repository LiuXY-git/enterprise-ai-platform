from pydantic import BaseModel, Field


class DocumentParseResponse(BaseModel):
    document_id: int = Field(
        ge=1,
        description="文档在 SQLite 数据库中的唯一编号。",
        examples=[12],
    )
    filename: str = Field(
        description="上传文件的原始名称。",
        examples=["architecture.md"],
    )
    content_type: str = Field(
        description="上传文件的 MIME 类型。",
        examples=["text/markdown"],
    )
    size: int = Field(
        ge=1,
        description="上传文件的大小，单位为字节。",
        examples=[340],
    )
    file_type: str = Field(
        description="平台识别出的文档类型。",
        examples=["markdown"],
    )
    status: str = Field(
        description="文档处理和索引状态。",
        examples=["indexed"],
    )
    text: str = Field(
        description="从文档中提取出的文本内容。",
        examples=["# 系统架构\n\n当前系统使用 FastAPI。"],
    )
    chunk_count: int = Field(
        ge=1,
        description="文档切分并写入向量数据库的片段数量。",
        examples=[2],
    )
    page_count: int | None = Field(
        default=None,
        ge=1,
        description="PDF 文档的页数，其他文档类型返回 null。",
        examples=[3],
    )
    paragraph_count: int | None = Field(
        default=None,
        ge=0,
        description="DOCX 文档的段落数，其他文档类型返回 null。",
        examples=[15],
    )
    line_count: int | None = Field(
        default=None,
        ge=0,
        description="Markdown 文档的行数，其他文档类型返回 null。",
        examples=[13],
    )
