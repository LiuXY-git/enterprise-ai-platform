import pymupdf


def extract_text_from_pdf(content: bytes) -> tuple[str, int]:
    try:
        with pymupdf.open(stream=content, filetype="pdf") as document:
            pages = [page.get_text(sort=True) for page in document]

            text = "\n".join(pages).strip()
            page_count = document.page_count

    except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
        raise ValueError("PDF 文件损坏或内容无效") from exc

    return text, page_count
