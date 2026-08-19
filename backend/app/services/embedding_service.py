from chromadb.utils.embedding_functions import (
    DefaultEmbeddingFunction,
)

_embedding_function = DefaultEmbeddingFunction()


def embed_texts(
    texts: list[str],
) -> list[list[float]]:
    if not texts:
        return []

    raw_embeddings = _embedding_function(texts)

    return [[float(value) for value in embedding] for embedding in raw_embeddings]
