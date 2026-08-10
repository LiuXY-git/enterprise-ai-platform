from pydantic import BaseModel


class DocumentParseResponse(BaseModel):
    filename: str
    content_type: str
    size: int
    file_type: str
    text: str
    page_count: int | None = None
    paragraph_count: int | None = None
