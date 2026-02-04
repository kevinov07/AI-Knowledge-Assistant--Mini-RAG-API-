import os
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


@lru_cache(maxsize=1)
def get_langchain_embeddings() -> HuggingFaceEmbeddings:
    """
    Instancia de HuggingFaceEmbeddings compatible con LangChain (FAISS, etc.).
    Se carga una sola vez en la primera llamada.
    """
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_embedding(text: str) -> list[float]:
    """Devuelve el embedding de un texto como lista de floats (compat con código existente)."""
    return get_langchain_embeddings().embed_query(text)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Devuelve una lista de embeddings para una lista de textos."""
    if not texts:
        return []
    return get_langchain_embeddings().embed_documents(texts)

