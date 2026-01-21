from sentence_transformers import SentenceTransformer
import numpy as np
import os
from functools import lru_cache

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

@lru_cache
def get_embedding_model():
    return SentenceTransformer(EMBEDDING_MODEL)

model = get_embedding_model()

def normalize_vector(vector: np.ndarray) -> np.ndarray:

    """
    Normaliza un vector dividiéndolo por su módulo.
    """
    module = np.linalg.norm(vector)
    if module == 0:
        return vector
    return vector / module


def get_embedding(text: str):
    """
    Recibe un texto y devuelve su embedding como lista de floats.
    """
    vector = np.array(model.encode(text))
    return normalize_vector(vector)

def get_embeddings(texts: list[str]):
    """
    Recibe una lista de textos y devuelve una lista de embeddings.
    """
    return [get_embedding(text) for text in texts]
