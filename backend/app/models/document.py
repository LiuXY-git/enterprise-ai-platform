from pydantic import BaseModel


class DocumentParseResponse(BaseModel):
    document_id: int
    filename: str
    content_type: str
    size: int
    file_type: str
    status: str
    text: str
    page_count: int | None = None
    paragraph_count: int | None = None
    line_count: int | None = None
