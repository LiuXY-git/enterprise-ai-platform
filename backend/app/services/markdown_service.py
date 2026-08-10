def extract_text_from_markdown(content: bytes) -> tuple[str, int]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Markdown 文件必须使用 UTF-8 编码") from exc

    text = text.strip()

    if not text:
        raise ValueError("Markdown 文件内容为空")

    line_count = len(text.splitlines())

    return text, line_count
