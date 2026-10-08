import re
from time import perf_counter

from backend.app.services.rag_service import answer_question

GOLDEN_CASES = [
    (
        "项目支持上传哪些文档格式？",
        "README.md",
    ),
    (
        "如何使用 Docker 启动项目？",
        "README.md",
    ),
    (
        "健康检查接口是什么？",
        "README.md",
    ),
    (
        "数据库保存了哪些文档信息？",
        "docs/week-2.md",
    ),
    (
        "当前项目版本是多少？",
        "README.md",
    ),
]


def citations_are_valid(
    answer: str,
    source_count: int,
) -> bool:
    citation_numbers = [
        int(value)
        for value in re.findall(
            r"\[来源(\d+)\]",
            answer,
        )
    ]

    if not citation_numbers:
        return False

    return all(1 <= number <= source_count for number in citation_numbers)


def main() -> None:
    passed_count = 0

    for question, expected_source in GOLDEN_CASES:
        started_at = perf_counter()

        result = answer_question(
            question,
            top_k=3,
        )

        elapsed = perf_counter() - started_at

        actual_sources = {chunk.source for chunk in result.chunks}

        source_passed = expected_source in actual_sources
        citation_passed = citations_are_valid(
            result.answer,
            len(result.chunks),
        )
        case_passed = source_passed and citation_passed

        if case_passed:
            passed_count += 1

        print("=" * 70)
        print("问题：", question)
        print("预期来源：", expected_source)
        print("实际来源：", sorted(actual_sources))
        print("回答：", result.answer)
        print("来源命中：", source_passed)
        print("引用有效：", citation_passed)
        print("耗时：", round(elapsed, 2), "秒")
        print("结果：", "通过" if case_passed else "失败")

    print("=" * 70)
    print(f"黄金问题通过：{passed_count}/{len(GOLDEN_CASES)}")

    if passed_count != len(GOLDEN_CASES):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
