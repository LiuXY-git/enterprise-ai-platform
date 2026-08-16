from collections import Counter
from math import sqrt

DOCUMENTS = {
    "leave_policy": "员工 申请 年假 休假",
    "docker_guide": "Docker 容器 启动 服务",
}

QUESTION = "员工 如何 申请 休假"


def build_vocabulary(texts: list[str]) -> list[str]:
    words = {word for text in texts for word in text.split()}
    return sorted(words)


def embed_text(
    text: str,
    vocabulary: list[str],
) -> list[float]:
    word_counts = Counter(text.split())

    return [float(word_counts.get(word, 0)) for word in vocabulary]


def cosine_similarity(
    first: list[float],
    second: list[float],
) -> float:
    dot_product = sum(left * right for left, right in zip(first, second, strict=True))

    first_length = sqrt(sum(value**2 for value in first))
    second_length = sqrt(sum(value**2 for value in second))

    if first_length == 0 or second_length == 0:
        return 0.0

    return dot_product / (first_length * second_length)


def main() -> None:
    all_texts = [
        *DOCUMENTS.values(),
        QUESTION,
    ]

    vocabulary = build_vocabulary(all_texts)
    question_vector = embed_text(QUESTION, vocabulary)

    print("词汇表：", vocabulary)
    print("问题：", QUESTION)
    print("问题向量：", question_vector)
    print()

    results: list[tuple[str, float]] = []

    for document_name, document_text in DOCUMENTS.items():
        document_vector = embed_text(
            document_text,
            vocabulary,
        )

        similarity = cosine_similarity(
            question_vector,
            document_vector,
        )

        results.append(
            (
                document_name,
                similarity,
            )
        )

        print("文档：", document_name)
        print("文本：", document_text)
        print("向量：", document_vector)
        print("相似度：", round(similarity, 4))
        print()

    results.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    print("检索结果：")

    for document_name, similarity in results:
        print(
            document_name,
            round(similarity, 4),
        )


if __name__ == "__main__":
    main()
