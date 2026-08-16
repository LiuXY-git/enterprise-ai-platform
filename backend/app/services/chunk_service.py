def split_by_paragraph(text: str) -> list[str]:
    normalized_text = text.replace("\r\n", "\n").strip()

    if not normalized_text:
        return []

    return [
        paragraph.strip()
        for paragraph in normalized_text.split("\n\n")
        if paragraph.strip()
    ]


def split_by_length(
    text: str,
    *,
    chunk_size: int,
    overlap: int = 0,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")

    if overlap < 0:
        raise ValueError("overlap 不能小于 0")

    if overlap >= chunk_size:
        raise ValueError("overlap 必须小于 chunk_size")

    normalized_text = text.strip()

    if not normalized_text:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(normalized_text):
        end = min(start + chunk_size, len(normalized_text))
        chunk = normalized_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == len(normalized_text):
            break

        start = end - overlap

    return chunks
