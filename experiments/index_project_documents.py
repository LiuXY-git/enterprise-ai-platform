from pathlib import Path

from backend.app.services.indexing_service import (
    index_document_text,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROJECT_DOCUMENTS = [
    (
        "readme",
        Path("README.md"),
    ),
    (
        "database",
        Path("docs/database.md"),
    ),
    (
        "week-2-summary",
        Path("docs/week-2-summary.md"),
    ),
]


def main() -> None:
    for document_id, relative_path in PROJECT_DOCUMENTS:
        file_path = PROJECT_ROOT / relative_path
        text = file_path.read_text(
            encoding="utf-8",
        )

        chunk_count = index_document_text(
            document_id=document_id,
            source=relative_path.as_posix(),
            text=text,
        )

        print(f"{relative_path.as_posix()}：{chunk_count} 个 Chunk")


if __name__ == "__main__":
    main()
