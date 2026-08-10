from io import BytesIO
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from docx.table import Table
from docx.text.paragraph import Paragraph


def extract_text_from_docx(content: bytes) -> tuple[str, int]:
    try:
        document = Document(BytesIO(content))
    except (BadZipFile, PackageNotFoundError, ValueError) as exc:
        raise ValueError("DOCX 文件损坏或内容无效") from exc

    parts: list[str] = []
    paragraph_count = 0

    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            text = block.text.strip()

            if text:
                parts.append(text)
                paragraph_count += 1

        elif isinstance(block, Table):
            for row in block.rows:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                row_text = "\t".join(cell for cell in cells if cell)

                if row_text:
                    parts.append(row_text)

    return "\n".join(parts), paragraph_count
