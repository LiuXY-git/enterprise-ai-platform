from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(
    prefix="/upload",
    tags=["documents"],
)


@router.post("")
async def upload_pdf(
    file: Annotated[UploadFile, File(description="请选择 PDF 文件")],
) -> dict[str, str | int]:
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="只支持上传 PDF 文件",
        )

    content = await file.read()

    return {
        "filename": file.filename or "",
        "content_type": file.content_type,
        "size": len(content),
    }
