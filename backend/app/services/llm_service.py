from openai import OpenAI, OpenAIError

from .llm_config import get_llm_config
from .prompt_service import SYSTEM_PROMPT, build_rag_input
from .retrieval_service import RetrievedChunk


def generate_grounded_answer(
    question: str,
    chunks: list[RetrievedChunk],
) -> str:
    config = get_llm_config()

    client = OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
    )

    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": build_rag_input(
                        question,
                        chunks,
                    ),
                },
            ],
        )
    except OpenAIError as exc:
        print(f"{config.provider} 原始错误：{type(exc).__name__}: {exc}")
        raise RuntimeError("LLM 调用失败") from exc

    answer = response.choices[0].message.content

    if not answer:
        raise RuntimeError("LLM 没有返回回答")

    return answer.strip()
