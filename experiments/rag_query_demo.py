from backend.app.services.retrieval_service import (
    search_chunks,
)

QUESTIONS = [
    "项目支持上传哪些文档格式？",
    "如何使用 Docker 启动项目？",
    "健康检查接口是什么？",
    "数据库保存了哪些文档信息？",
    "当前项目版本是多少？",
]


def main() -> None:
    for question in QUESTIONS:
        print("=" * 60)
        print("问题：", question)

        results = search_chunks(
            question,
            top_k=3,
        )

        for rank, result in enumerate(
            results,
            start=1,
        ):
            preview = result.text.replace(
                "\n",
                " ",
            )[:120]

            print()
            print(f"第 {rank} 名")
            print("来源：", result.source)
            print("Chunk：", result.chunk_index)
            print(
                "距离：",
                round(result.distance, 4),
            )
            print("内容：", preview)


if __name__ == "__main__":
    main()
