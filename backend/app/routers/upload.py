from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..models.document import PdfParseResponse
from ..services.pdf_service import extract_text_from_pdf

router = APIRouter(
    prefix="/upload",
    tags=["documents"],
)


@router.post("", response_model=PdfParseResponse)
async def upload_pdf(
    file: Annotated[UploadFile, File(description="请选择 PDF 文件")],
) -> PdfParseResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="只支持上传 PDF 文件",
        )

    content = await file.read()

    try:
        text, page_count = extract_text_from_pdf(content)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return PdfParseResponse(
        filename=file.filename or "",
        content_type=file.content_type,
        size=len(content),
        page_count=page_count,
        text=text,
    )
