"""
Índice FAISS usando LangChain.

Unifica documentos + embeddings + FAISS en un solo vectorstore:
  vectorstore = FAISS.from_documents(documents=splits, embedding=embeddings)
  vectorstore.add_documents(new_docs)  # subidas posteriores
"""
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS

# Vectorstore global (único índice para upload y búsqueda)
_vectorstore: Optional[FAISS] = None


def is_initialized() -> bool:
    """Indica si el vectorstore FAISS está creado."""
    return _vectorstore is not None


def get_vectorstore() -> Optional[FAISS]:
    """Devuelve el vectorstore FAISS actual."""
    return _vectorstore


def init_vectorstore(documents: List[Document], embedding: Embeddings) -> FAISS:
    """
    Crea el índice FAISS desde una lista de documentos (primera subida).
    Usa FAISS.from_documents(documents, embedding).
    """
    global _vectorstore
    _vectorstore = FAISS.from_documents(documents=documents, embedding=embedding)
    return _vectorstore


def add_documents(documents: List[Document]) -> None:
    """
    Añade documentos al vectorstore existente (subidas posteriores).
    """
    global _vectorstore
    if _vectorstore is None:
        raise RuntimeError("Vectorstore no inicializado. Llama a init_vectorstore primero.")
    _vectorstore.add_documents(documents=documents)


def reset_vectorstore() -> None:
    """Limpia el vectorstore (para reset / reindexar)."""
    global _vectorstore
    _vectorstore = None
