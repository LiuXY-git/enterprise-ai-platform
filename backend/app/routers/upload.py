from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..database import create_document
from ..models.document import DocumentParseResponse
from ..services.markdown_service import extract_text_from_markdown
from ..services.pdf_service import extract_text_from_pdf
from ..services.word_service import extract_text_from_docx

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
MARKDOWN_SUFFIXES = {".md", ".markdown"}

router = APIRouter(
    prefix="/upload",
    tags=["documents"],
)


@router.post("", response_model=DocumentParseResponse)
async def upload_document(
    file: Annotated[
        UploadFile,
        File(description="请选择 PDF、DOCX 或 Markdown 文件"),
    ],
) -> DocumentParseResponse:
    filename = file.filename or ""
    content_type = file.content_type or "application/octet-stream"
    suffix = Path(filename).suffix.lower()
    content = await file.read()
    size = len(content)
    status = "parsed"

    try:
        if suffix == ".pdf" or content_type == "application/pdf":
            text, page_count = extract_text_from_pdf(content)

            document_id = create_document(
                filename=filename,
                file_type="pdf",
                content_type=content_type,
                size=size,
                status=status,
            )

            return DocumentParseResponse(
                document_id=document_id,
                filename=filename,
                content_type=content_type,
                size=size,
                file_type="pdf",
                status=status,
                page_count=page_count,
                text=text,
            )

        if suffix == ".docx" or content_type == DOCX_CONTENT_TYPE:
            text, paragraph_count = extract_text_from_docx(content)

            document_id = create_document(
                filename=filename,
                file_type="docx",
                content_type=content_type,
                size=size,
                status=status,
            )

            return DocumentParseResponse(
                document_id=document_id,
                filename=filename,
                content_type=content_type,
                size=size,
                file_type="docx",
                status=status,
                paragraph_count=paragraph_count,
                text=text,
            )

        if suffix in MARKDOWN_SUFFIXES:
            text, line_count = extract_text_from_markdown(content)

            document_id = create_document(
                filename=filename,
                file_type="markdown",
                content_type=content_type,
                size=size,
                status=status,
            )

            return DocumentParseResponse(
                document_id=document_id,
                filename=filename,
                content_type=content_type,
                size=size,
                file_type="markdown",
                status=status,
                line_count=line_count,
                text=text,
            )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    raise HTTPException(
        status_code=400,
        detail="只支持 PDF、DOCX 和 Markdown 文件",
    )
