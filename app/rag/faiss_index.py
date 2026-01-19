import faiss
import numpy as np

index = None
DIMENSION = None

def init_index(dimension: int):
    global index, DIMENSION
    if index is None:
        DIMENSION = dimension
        index = faiss.IndexFlatIP(dimension)

def add_embeddings(embeddings: np.ndarray):
    index.add(embeddings)

def is_initialized():
    return index is not None

def search_embeddings(query_embedding: np.ndarray, k: int = 5):
    return index.search(query_embedding, k)












# import faiss
# import numpy as np
# from app.rag.documents import DOCUMENTS
# from app.rag.embeddings import get_embeddings

# def build_index():
#     embeddings = np.array(get_embeddings(DOCUMENTS)).astype("float32")

#     print("🔍 Construyendo índice FAISS...", embeddings)
#     dimension = embeddings.shape[1]
#     index = faiss.IndexFlatIP(dimension)
#     index.add(embeddings)

#     return index, embeddings

# if __name__ == "__main__":
#     index, embeddings = build_index()

#     print("📌 DOCUMENTOS:")
#     for i, doc in enumerate(DOCUMENTS):
#         print(f"{i}: {doc[:60]}...")

#     print("\n📐 Shape de embeddings:", embeddings.shape)
#     print("📦 Total en FAISS:", index.ntotal)
