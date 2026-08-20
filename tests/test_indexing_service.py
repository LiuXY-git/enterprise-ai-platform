from backend.app.services import indexing_service


class FakeCollection:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def upsert(self, **kwargs) -> None:
        self.calls.append(kwargs)


def test_multiple_documents_use_distinct_chunk_ids(
    monkeypatch,
) -> None:
    collection = FakeCollection()

    monkeypatch.setattr(
        indexing_service,
        "split_by_length",
        lambda text, *, chunk_size, overlap: [
            f"{text}-第一段",
            f"{text}-第二段",
        ],
    )
    monkeypatch.setattr(
        indexing_service,
        "embed_texts",
        lambda chunks: [
            [0.1, 0.2],
            [0.3, 0.4],
        ],
    )
    monkeypatch.setattr(
        indexing_service,
        "get_document_chunks_collection",
        lambda: collection,
    )

    first_count = indexing_service.index_document_text(
        document_id="101",
        source="first.md",
        text="第一份文档",
    )
    second_count = indexing_service.index_document_text(
        document_id="102",
        source="second.md",
        text="第二份文档",
    )

    assert first_count == 2
    assert second_count == 2

    assert collection.calls[0]["ids"] == [
        "101-chunk-0",
        "101-chunk-1",
    ]
    assert collection.calls[1]["ids"] == [
        "102-chunk-0",
        "102-chunk-1",
    ]

    assert collection.calls[0]["metadatas"][0]["document_id"] == "101"
    assert collection.calls[1]["metadatas"][0]["document_id"] == "102"
