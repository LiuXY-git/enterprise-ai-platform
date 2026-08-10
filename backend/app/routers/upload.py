from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..models.document import DocumentParseResponse
from ..services.pdf_service import extract_text_from_pdf
from ..services.word_service import extract_text_from_docx

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

router = APIRouter(
    prefix="/upload",
    tags=["documents"],
)


@router.post("", response_model=DocumentParseResponse)
async def upload_document(
    file: Annotated[
        UploadFile,
        File(description="请选择 PDF 或 DOCX 文件"),
    ],
) -> DocumentParseResponse:
    filename = file.filename or ""
    content_type = file.content_type or "application/octet-stream"
    suffix = Path(filename).suffix.lower()
    content = await file.read()

    try:
        if suffix == ".pdf" or content_type == "application/pdf":
            text, page_count = extract_text_from_pdf(content)

            return DocumentParseResponse(
                filename=filename,
                content_type=content_type,
                size=len(content),
                file_type="pdf",
                page_count=page_count,
                text=text,
            )

        if suffix == ".docx" or content_type == DOCX_CONTENT_TYPE:
            text, paragraph_count = extract_text_from_docx(content)

            return DocumentParseResponse(
                filename=filename,
                content_type=content_type,
                size=len(content),
                file_type="docx",
                paragraph_count=paragraph_count,
                text=text,
            )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    raise HTTPException(
        status_code=400,
        detail="只支持 PDF 和 DOCX 文件",
    )
