from pydantic import BaseModel


class PdfParseResponse(BaseModel):
    filename: str
    content_type: str
    size: int
    page_count: int
    text: str
