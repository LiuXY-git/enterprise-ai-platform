from pathlib import Path

from backend.app.services.chunk_service import (
    split_by_length,
    split_by_paragraph,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = PROJECT_ROOT / "docs" / "week-2.md"


def print_chunks(name: str, chunks: list[str]) -> None:
    print(f"\n=== {name} ===")
    print(f"Chunk 数量：{len(chunks)}")

    for index, chunk in enumerate(chunks, start=1):
        preview = chunk.replace("\n", " ")[:100]
        print(f"{index}. 长度={len(chunk)} | {preview}")


def main() -> None:
    text = SOURCE_FILE.read_text(encoding="utf-8")

    paragraph_chunks = split_by_paragraph(text)

    fixed_chunks = split_by_length(
        text,
        chunk_size=200,
        overlap=0,
    )

    overlap_chunks = split_by_length(
        text,
        chunk_size=200,
        overlap=50,
    )

    large_chunks = split_by_length(
        text,
        chunk_size=400,
        overlap=50,
    )

    print(f"源文件：{SOURCE_FILE.name}")
    print(f"总字符数：{len(text)}")

    print_chunks("按段落切分", paragraph_chunks)
    print_chunks("固定长度 200，无重叠", fixed_chunks)
    print_chunks("固定长度 200，重叠 50", overlap_chunks)
    print_chunks("固定长度 400，重叠 50", large_chunks)


if __name__ == "__main__":
    main()
