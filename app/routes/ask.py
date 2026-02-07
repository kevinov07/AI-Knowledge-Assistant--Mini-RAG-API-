"""
Endpoint para consultas RAG: búsqueda semántica + expansión de contexto + respuesta con LLM.
"""
import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.models import Chunk
from app.llm.groq_client import generate_answer
from app.schemas import QuestionRequest
from app.db.database import get_db
from app.rag.embeddings import get_embedding
from app.rag.retriever import (
    similarity_search_chunks_pgvector,
    get_context_chunks_from_db,
)
# Código FAISS/store (comentado al usar pgvector + BD):
# from app.rag.vectorstore import get_vectorstore, is_initialized
# from app.rag.retriever import get_context_chunks
# from app.rag.store import CHUNKS_METADATA

MAX_CONTEXT_CHARS = int(os.getenv("GROQ_MAX_CONTEXT_CHARS", "32000"))

router = APIRouter()


@router.post(
    "/ask",
    summary="Hacer una pregunta sobre los documentos",
    response_description="Pregunta, respuesta generada y chunks recuperados con sus scores.",
)
async def ask_question(request: QuestionRequest, db: Session = Depends(get_db)):
    """
    Responde una pregunta usando **búsqueda semántica** sobre los documentos indexados.

    Flujo:
    1. Recupera los `k` chunks más similares a la pregunta (pgvector + embeddings).
    2. Expande el contexto con chunks vecinos (±2) desde la BD para no cortar ideas a mitad.
    3. Trunca el contexto total si supera el límite del modelo (evita payload too large).
    4. Genera la respuesta con Groq LLM usando solo ese contexto.

    **Requisito:** Debe haber documentos subidos previamente (`POST /api/upload`).
    Si no hay chunks en la BD, devuelve error indicándolo.

    **Respuesta:**
    - `question`: la pregunta enviada.
    - `answer`: texto generado por el LLM.
    - `results`: los **k chunks más similares** (semillas de la búsqueda), con `text`, `document_id`, `chunk_index` y `score`.
    - `context_used`: los **fragmentos de texto realmente enviados al LLM** (semillas + vecinos ±2 por cada una, sin duplicados, posiblemente truncados por límite del modelo). Es el contexto con el que se generó la respuesta.
    """
    # Comprobar que hay chunks en la BD (equivalente a is_initialized() con FAISS)
    # if db.execute(text("SELECT 1 FROM chunks LIMIT 1")).fetchone() is None:
    #     return {"error": "No hay documentos indexados. Por favor, suba documentos primero."}
    if not db.query(Chunk).first():
        return {"error": "No hay documentos indexados. Por favor, suba documentos primero."}

    # Búsqueda por similitud con pgvector (equivalente a similarity_search_with_score de FAISS)
    docs_with_scores = similarity_search_chunks_pgvector(
        db, request.question, k=request.k, get_embedding=get_embedding
    )

    # Código FAISS (comentado):
    # if not is_initialized():
    #     return {"error": "El vectorstore no está inicializado. Por favor, suba documentos primero."}
    # vectorstore = get_vectorstore()
    # docs_with_scores = vectorstore.similarity_search_with_score(request.question, k=request.k)

    results = []
    all_context_chunks = []

    for doc, score in docs_with_scores:
        meta = doc.metadata
        document_id = meta.get("document_id", "")
        chunk_index = meta.get("chunk_index", 0)
        chunk_text = doc.page_content

        # Expansión de contexto desde la BD (chunks vecinos ±2)
        context_chunks = get_context_chunks_from_db(
            db, document_id, chunk_index, window=2
        )
        all_context_chunks.extend(context_chunks)

        # Código store en memoria (comentado):
        # context_chunks = get_context_chunks(
        #     CHUNKS_METADATA,
        #     document_id,
        #     chunk_index,
        #     window=2,
        # )
        # all_context_chunks.extend(context_chunks)

        results.append({
            "text": chunk_text,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "score": float(score),
        })

    unique_chunks = list(dict.fromkeys(all_context_chunks))
    sep = "\n---\n"
    context_parts = []
    total_len = 0
    for c in unique_chunks:
        add_len = (len(sep) if context_parts else 0) + len(c)
        if total_len + add_len > MAX_CONTEXT_CHARS and context_parts:
            break
        context_parts.append(c)
        total_len += add_len
    context_for_llm = sep.join(context_parts)
    if len(unique_chunks) > len(context_parts):
        context_for_llm += "\n\n[... contexto truncado por límite del modelo ...]"

    answer = generate_answer(question=request.question, context=context_for_llm)

    # context_used: lo que realmente vio el LLM (semillas + vecinos), para transparencia
    return {
        "question": request.question,
        "answer": answer,
        "results": results,
        "context_used": context_parts,
    }