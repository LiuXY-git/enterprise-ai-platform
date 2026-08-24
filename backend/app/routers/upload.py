import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..database import create_document, update_document_status
from ..logging_config import LOGGER_NAME
from ..models.document import DocumentParseResponse
from ..services.indexing_service import index_document_text
from ..services.markdown_service import extract_text_from_markdown
from ..services.pdf_service import extract_text_from_pdf
from ..services.word_service import extract_text_from_docx

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
MARKDOWN_SUFFIXES = {".md", ".markdown"}

logger = logging.getLogger(f"{LOGGER_NAME}.upload")

router = APIRouter(
    prefix="/upload",
    tags=["documents"],
)


@router.post(
    "",
    response_model=DocumentParseResponse,
    summary="上传并索引文档",
    description=(
        "上传 PDF、DOCX 或 Markdown 文档。平台会自动提取文本、"
        "保存文档元数据、切分文本、生成 Embedding 并写入 Chroma。"
        "接口成功返回时，文档已经可以参与 RAG 检索。"
    ),
    response_description="文档解析结果及向量索引信息。",
    responses={
        400: {
            "description": "文件为空、无法读取或文档解析失败。",
        },
        415: {
            "description": "上传了不支持的文件类型。",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "只支持 PDF、DOCX 和 Markdown 文件",
                    },
                },
            },
        },
        422: {
            "description": "请求中缺少 file 字段。",
        },
        500: {
            "description": "文档保存或向量索引过程发生服务器错误。",
        },
    },
)
async def upload_document(
    file: Annotated[
        UploadFile,
        File(description="请选择 PDF、DOCX 或 Markdown 文件"),
    ],
) -> DocumentParseResponse:
    filename = file.filename or ""
    content_type = file.content_type or "application/octet-stream"
    suffix = Path(filename).suffix.lower()

    logger.info(
        "收到上传请求：filename=%s, content_type=%s",
        filename,
        content_type,
    )

    if not filename:
        logger.warning("上传失败：文件名为空")
        raise HTTPException(
            status_code=400,
            detail="文件名不能为空",
        )

    try:
        content = await file.read()
    except Exception as exc:
        logger.exception("读取上传文件失败：filename=%s", filename)
        raise HTTPException(
            status_code=400,
            detail="无法读取上传文件",
        ) from exc

    size = len(content)

    if size == 0:
        logger.warning("上传失败：文件内容为空，filename=%s", filename)
        raise HTTPException(
            status_code=400,
            detail="文件内容不能为空",
        )

    if suffix == ".pdf" or content_type == "application/pdf":
        file_type = "pdf"
    elif suffix == ".docx" or content_type == DOCX_CONTENT_TYPE:
        file_type = "docx"
    elif suffix in MARKDOWN_SUFFIXES:
        file_type = "markdown"
    else:
        logger.warning(
            "上传失败：不支持的文件类型，filename=%s, content_type=%s",
            filename,
            content_type,
        )
        raise HTTPException(
            status_code=415,
            detail="只支持 PDF、DOCX 和 Markdown 文件",
        )

    page_count = None
    paragraph_count = None
    line_count = None

    try:
        if file_type == "pdf":
            text, page_count = extract_text_from_pdf(content)
        elif file_type == "docx":
            text, paragraph_count = extract_text_from_docx(content)
        else:
            text, line_count = extract_text_from_markdown(content)

        document_id = create_document(
            filename=filename,
            file_type=file_type,
            content_type=content_type,
            size=size,
            status="indexing",
        )

        try:
            chunk_count = index_document_text(
                document_id=str(document_id),
                source=filename,
                text=text,
            )
        except Exception:
            update_document_status(
                document_id=document_id,
                status="index_failed",
            )
            raise

        if chunk_count == 0:
            update_document_status(
                document_id=document_id,
                status="index_failed",
            )
            raise ValueError("文档没有可索引的文本")

        update_document_status(
            document_id=document_id,
            status="indexed",
        )

    except ValueError as exc:
        logger.warning(
            "文档解析失败：filename=%s, error=%s",
            filename,
            exc,
        )
        raise HTTPException(
            status_code=400,
            detail=f"文档解析失败：{exc}",
        ) from exc

    except Exception as exc:
        logger.exception(
            "处理文档时发生服务器错误：filename=%s",
            filename,
        )
        raise HTTPException(
            status_code=500,
            detail="服务器处理文档时发生错误",
        ) from exc

    logger.info(
        ("文档处理成功：document_id=%s, filename=%s, file_type=%s, chunk_count=%s"),
        document_id,
        filename,
        file_type,
        chunk_count,
    )

    return DocumentParseResponse(
        document_id=document_id,
        filename=filename,
        content_type=content_type,
        size=size,
        file_type=file_type,
        status="indexed",
        text=text,
        chunk_count=chunk_count,
        page_count=page_count,
        paragraph_count=paragraph_count,
        line_count=line_count,
    )
