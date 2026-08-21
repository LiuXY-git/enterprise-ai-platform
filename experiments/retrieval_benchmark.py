from dataclasses import dataclass
from pathlib import Path

import chromadb

from backend.app.services.chunk_service import split_by_length
from backend.app.services.embedding_service import embed_texts

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DOCUMENT_PATHS = (
    Path("README.md"),
    Path("docs/database.md"),
    Path("docs/week-2-summary.md"),
    Path("docs/architecture.md"),
    Path("docs/week-3-summary.md"),
)


@dataclass(frozen=True)
class GoldenCase:
    question: str
    expected_sources: frozenset[str]


@dataclass(frozen=True)
class BenchmarkConfig:
    chunk_size: int
    overlap: int
    top_k: int


GOLDEN_CASES = (
    GoldenCase(
        question="项目支持上传哪些文档格式？",
        expected_sources=frozenset(
            {
                "README.md",
                "docs/week-2-summary.md",
            }
        ),
    ),
    GoldenCase(
        question="如何使用 Docker 启动项目？",
        expected_sources=frozenset(
            {
                "README.md",
            }
        ),
    ),
    GoldenCase(
        question="健康检查接口是什么？",
        expected_sources=frozenset(
            {
                "README.md",
            }
        ),
    ),
    GoldenCase(
        question="数据库保存了哪些文档信息？",
        expected_sources=frozenset(
            {
                "docs/database.md",
                "docs/week-2-summary.md",
            }
        ),
    ),
    GoldenCase(
        question="当前项目版本是多少？",
        expected_sources=frozenset(
            {
                "README.md",
            }
        ),
    ),
    GoldenCase(
        question="Docker、FastAPI、Routers 和 Services 之间是什么关系？",
        expected_sources=frozenset(
            {
                "docs/architecture.md",
            }
        ),
    ),
    GoldenCase(
        question="Week 3 完成了哪些 RAG 功能？",
        expected_sources=frozenset(
            {
                "docs/week-3-summary.md",
            }
        ),
    ),
)

BENCHMARK_CONFIGS = (
    BenchmarkConfig(
        chunk_size=200,
        overlap=0,
        top_k=3,
    ),
    BenchmarkConfig(
        chunk_size=200,
        overlap=50,
        top_k=1,
    ),
    BenchmarkConfig(
        chunk_size=200,
        overlap=50,
        top_k=3,
    ),
    BenchmarkConfig(
        chunk_size=200,
        overlap=50,
        top_k=5,
    ),
    BenchmarkConfig(
        chunk_size=300,
        overlap=50,
        top_k=3,
    ),
    BenchmarkConfig(
        chunk_size=400,
        overlap=50,
        top_k=3,
    ),
)


def build_collection(
    config: BenchmarkConfig,
):
    client = chromadb.EphemeralClient()

    collection = client.create_collection(
        name=(f"benchmark_{config.chunk_size}_{config.overlap}_{config.top_k}"),
        embedding_function=None,
    )

    record_ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for document_number, relative_path in enumerate(
        DOCUMENT_PATHS,
        start=1,
    ):
        file_path = PROJECT_ROOT / relative_path
        text = file_path.read_text(encoding="utf-8")

        chunks = split_by_length(
            text,
            chunk_size=config.chunk_size,
            overlap=config.overlap,
        )

        for chunk_index, chunk in enumerate(chunks):
            record_ids.append(f"{document_number}-chunk-{chunk_index}")
            documents.append(chunk)
            metadatas.append(
                {
                    "source": relative_path.as_posix(),
                    "chunk_index": chunk_index,
                    "chunk_size": config.chunk_size,
                    "overlap": config.overlap,
                }
            )

    embeddings = embed_texts(documents)

    collection.upsert(
        ids=record_ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return collection


def evaluate_config(
    config: BenchmarkConfig,
    question_embeddings: list[list[float]],
) -> None:
    collection = build_collection(config)

    hit_count = 0
    reciprocal_rank_total = 0.0

    print("=" * 80)
    print(
        "参数：",
        f"chunk_size={config.chunk_size}",
        f"overlap={config.overlap}",
        f"top_k={config.top_k}",
    )

    for case, question_embedding in zip(
        GOLDEN_CASES,
        question_embeddings,
        strict=True,
    ):
        query_result = collection.query(
            query_embeddings=[question_embedding],
            n_results=min(
                config.top_k,
                collection.count(),
            ),
            include=[
                "metadatas",
                "distances",
            ],
        )

        raw_metadatas = (
            query_result["metadatas"][0] if query_result["metadatas"] else []
        )

        sources = [
            str((metadata or {}).get("source", "unknown")) for metadata in raw_metadatas
        ]

        rank = next(
            (
                position
                for position, source in enumerate(
                    sources,
                    start=1,
                )
                if source in case.expected_sources
            ),
            None,
        )

        if rank is not None:
            hit_count += 1
            reciprocal_rank_total += 1 / rank

        rank_text = str(rank) if rank is not None else "-"

        print()
        print("问题：", case.question)
        print("排名：", rank_text)
        print("来源：", sources)

    mean_reciprocal_rank = reciprocal_rank_total / len(GOLDEN_CASES)

    print()
    print(
        "SUMMARY",
        f"chunk_size={config.chunk_size}",
        f"overlap={config.overlap}",
        f"top_k={config.top_k}",
        f"chunks={collection.count()}",
        f"hit={hit_count}/{len(GOLDEN_CASES)}",
        f"mrr={mean_reciprocal_rank:.3f}",
    )


def main() -> None:
    question_embeddings = embed_texts([case.question for case in GOLDEN_CASES])

    for config in BENCHMARK_CONFIGS:
        evaluate_config(
            config,
            question_embeddings,
        )


if __name__ == "__main__":
    main()
