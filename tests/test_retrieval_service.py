from backend.app.services import retrieval_service


class FakeCollection:
    def count(self) -> int:
        return 5

    def query(
        self,
        *,
        query_embeddings,
        n_results: int,
        include,
    ) -> dict:
        assert query_embeddings == [[0.1, 0.2]]
        assert n_results == 5
        assert include == [
            "documents",
            "metadatas",
            "distances",
        ]

        return {
            "ids": [
                [
                    "document-1-chunk-0",
                    "document-2-chunk-0",
                    "document-3-chunk-0",
                    "document-4-chunk-0",
                    "document-5-chunk-0",
                ]
            ],
            "documents": [
                [
                    "项目支持 PDF、DOCX 和 Markdown。",
                    "项目支持 PDF、DOCX 和 Markdown。",
                    "数据库保存文档元数据。",
                    "系统采用分层架构。",
                    "Week 3 完成 RAG 功能。",
                ]
            ],
            "metadatas": [
                [
                    {
                        "source": "README.md",
                        "chunk_index": 0,
                    },
                    {
                        "source": "README.md",
                        "chunk_index": 0,
                    },
                    {
                        "source": "docs/database.md",
                        "chunk_index": 0,
                    },
                    {
                        "source": "docs/architecture.md",
                        "chunk_index": 0,
                    },
                    {
                        "source": "docs/week-3-summary.md",
                        "chunk_index": 0,
                    },
                ]
            ],
            "distances": [
                [
                    0.1,
                    0.1,
                    0.2,
                    0.3,
                    0.4,
                ]
            ],
        }


def test_search_chunks_removes_duplicate_content(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        retrieval_service,
        "get_document_chunks_collection",
        lambda: FakeCollection(),
    )
    monkeypatch.setattr(
        retrieval_service,
        "embed_texts",
        lambda texts: [[0.1, 0.2]],
    )

    results = retrieval_service.search_chunks(
        "项目支持哪些文档格式？",
        top_k=3,
    )

    assert len(results) == 3
    assert [result.id for result in results] == [
        "document-1-chunk-0",
        "document-3-chunk-0",
        "document-4-chunk-0",
    ]
    assert [result.source for result in results] == [
        "README.md",
        "docs/database.md",
        "docs/architecture.md",
    ]
