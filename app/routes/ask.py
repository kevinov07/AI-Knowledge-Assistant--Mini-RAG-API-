"""
Endpoint para consultas RAG: búsqueda semántica + expansión de contexto + respuesta con LLM.
"""
import os

from fastapi import APIRouter
from app.llm.groq_client import generate_answer
from app.schemas import QuestionRequest
from app.rag.vectorstore import get_vectorstore, is_initialized
from app.rag.retriever import get_context_chunks
from app.rag.store import CHUNKS_METADATA

MAX_CONTEXT_CHARS = int(os.getenv("GROQ_MAX_CONTEXT_CHARS", "32000"))

router = APIRouter()


@router.post(
    "/ask",
    summary="Hacer una pregunta sobre los documentos",
    response_description="Pregunta, respuesta generada y chunks recuperados con sus scores.",
)
async def ask_question(request: QuestionRequest):
    """
    Responde una pregunta usando **búsqueda semántica** sobre los documentos indexados.

    Flujo:
    1. Recupera los `k` chunks más similares a la pregunta (FAISS + embeddings).
    2. Expande el contexto con chunks vecinos (±2) para no cortar ideas a mitad.
    3. Trunca el contexto total si supera el límite del modelo (evita payload too large).
    4. Genera la respuesta con Groq LLM usando solo ese contexto.

    **Requisito:** Debe haber documentos subidos previamente (`POST /api/upload`).
    Si el vectorstore no está inicializado, devuelve error indicándolo.

    **Respuesta:**
    - `question`: la pregunta enviada.
    - `answer`: texto generado por el LLM.
    - `results`: lista de chunks recuperados, cada uno con `text`, `document_id`, `chunk_index` y `score`.
    """
    if not is_initialized():
        return {"error": "El vectorstore no está inicializado. Por favor, suba documentos primero."}

    vectorstore = get_vectorstore()
    # LangChain devuelve lista de (Document, score)
    docs_with_scores = vectorstore.similarity_search_with_score(request.question, k=request.k)

    results = []
    all_context_chunks = []

    for doc, score in docs_with_scores:
        meta = doc.metadata
        document_id = meta.get("document_id", "")
        chunk_index = meta.get("chunk_index", 0)
        text = doc.page_content

        context_chunks = get_context_chunks(
            CHUNKS_METADATA,
            document_id,
            chunk_index,
            window=2,  # ±2 vecinos para no perder bloques intermedios (ej. principios 2–4)
        )
        all_context_chunks.extend(context_chunks)

        results.append({
            "text": text,
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

    return {
        "question": request.question,
        "answer": answer,
        "results": results,
    }