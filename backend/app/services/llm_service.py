import os

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from .prompt_service import SYSTEM_PROMPT, build_rag_input
from .retrieval_service import RetrievedChunk

load_dotenv()


def generate_grounded_answer(
    question: str,
    chunks: list[RetrievedChunk],
) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    base_url = os.getenv(
        "DEEPSEEK_BASE_URL",
        "https://api.deepseek.com",
    ).strip()
    model = os.getenv(
        "DEEPSEEK_MODEL",
        "deepseek-v4-flash",
    ).strip()

    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": build_rag_input(question, chunks),
                },
            ],
        )
    except OpenAIError as exc:
        print(f"DeepSeek 原始错误：{type(exc).__name__}: {exc}")
        raise RuntimeError("LLM 调用失败") from exc

    answer = response.choices[0].message.content

    if not answer:
        raise RuntimeError("LLM 没有返回回答")

    return answer.strip()
