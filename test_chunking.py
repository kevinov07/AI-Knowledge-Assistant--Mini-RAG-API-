from app.rag.chunking import chunk_text

text = """
FastAPI es un framework moderno para construir APIs rápidas.
Utiliza ASGI y permite alto rendimiento.
Uvicorn es el servidor más común para ejecutarlo.
FAISS permite buscar embeddings de forma eficiente.
"""

chunks = chunk_text(text, chunk_size=10, overlap=3)

for i, chunk in enumerate(chunks):
    print(f"\nChunk {i}:")
    print(chunk)
