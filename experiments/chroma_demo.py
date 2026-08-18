from backend.app.services.vector_store import (
    CHROMA_DATA_PATH,
    get_document_collection,
)

RECORD_IDS = [
    "leave-policy-0",
    "docker-guide-0",
]

DOCUMENTS = [
    "员工申请年假，需要提前三天提交申请。",
    "Docker 容器可以使用 docker compose up 启动。",
]

EMBEDDINGS = [
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
]

METADATAS = [
    {
        "source": "employee-handbook.md",
        "chunk_index": 0,
    },
    {
        "source": "docker-guide.md",
        "chunk_index": 0,
    },
]


def main() -> None:
    collection = get_document_collection()

    collection.upsert(
        ids=RECORD_IDS,
        documents=DOCUMENTS,
        embeddings=EMBEDDINGS,
        metadatas=METADATAS,
    )

    result = collection.get(
        ids=RECORD_IDS,
        include=[
            "documents",
            "metadatas",
            "embeddings",
        ],
    )

    documents = result["documents"] or []
    metadatas = result["metadatas"] or []
    embeddings = result["embeddings"]

    print("Chroma 保存位置：", CHROMA_DATA_PATH)
    print("Collection：", collection.name)
    print("记录总数：", collection.count())
    print()

    for index, record_id in enumerate(result["ids"]):
        stored_embedding = (
            [float(value) for value in embeddings[index]]
            if embeddings is not None
            else []
        )

        print("ID：", record_id)
        print("文本：", documents[index])
        print("来源：", metadatas[index])
        print("向量：", stored_embedding)
        print()


if __name__ == "__main__":
    main()
