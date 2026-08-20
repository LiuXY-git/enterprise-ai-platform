from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import upload as upload_router

app = FastAPI()
app.include_router(upload_router.router)

client = TestClient(app)


def test_upload_document_indexes_extracted_text(
    monkeypatch,
) -> None:
    statuses: list[tuple[int, str]] = []

    monkeypatch.setattr(
        upload_router,
        "extract_text_from_markdown",
        lambda content: (
            "第一份企业知识库文档",
            1,
        ),
    )
    monkeypatch.setattr(
        upload_router,
        "create_document",
        lambda **kwargs: 101,
    )

    def fake_index_document_text(**kwargs) -> int:
        assert kwargs["document_id"] == "101"
        assert kwargs["source"] == "first.md"
        assert kwargs["text"] == "第一份企业知识库文档"
        return 2

    monkeypatch.setattr(
        upload_router,
        "index_document_text",
        fake_index_document_text,
    )
    monkeypatch.setattr(
        upload_router,
        "update_document_status",
        lambda **kwargs: statuses.append(
            (
                kwargs["document_id"],
                kwargs["status"],
            )
        ),
    )

    response = client.post(
        "/upload",
        files={
            "file": (
                "first.md",
                b"# First document",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["document_id"] == 101
    assert body["filename"] == "first.md"
    assert body["status"] == "indexed"
    assert body["chunk_count"] == 2
    assert statuses == [
        (
            101,
            "indexed",
        )
    ]


def test_upload_marks_document_when_indexing_fails(
    monkeypatch,
) -> None:
    statuses: list[tuple[int, str]] = []

    monkeypatch.setattr(
        upload_router,
        "extract_text_from_markdown",
        lambda content: (
            "索引失败测试文档",
            1,
        ),
    )
    monkeypatch.setattr(
        upload_router,
        "create_document",
        lambda **kwargs: 102,
    )

    def fail_indexing(**kwargs) -> int:
        raise RuntimeError("向量数据库不可用")

    monkeypatch.setattr(
        upload_router,
        "index_document_text",
        fail_indexing,
    )
    monkeypatch.setattr(
        upload_router,
        "update_document_status",
        lambda **kwargs: statuses.append(
            (
                kwargs["document_id"],
                kwargs["status"],
            )
        ),
    )

    response = client.post(
        "/upload",
        files={
            "file": (
                "failed.md",
                b"# Failed document",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 500
    assert statuses == [
        (
            102,
            "index_failed",
        )
    ]
