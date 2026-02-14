"""
Endpoint para consultas RAG: búsqueda semántica + expansión de contexto + respuesta con LLM.
Soporta historial de chat por session_id (guardado en BD) o enviado en el body.
Si el cliente no envía session_id, el backend crea uno y lo devuelve para las siguientes peticiones.
"""
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Chunk, ChatMessage, Session as SessionModel
from app.llm.groq_client import generate_answer
from app.schemas import QuestionRequest, AskResponse
from app.db.database import get_db
from app.rag.embeddings import get_embedding
from app.rag.retriever import (
    similarity_search_chunks_pgvector,
    get_context_chunks_from_db,
)

MAX_CONTEXT_CHARS = int(os.getenv("GROQ_MAX_CONTEXT_CHARS", "32000"))
MAX_HISTORY_LOAD = int(os.getenv("ASK_MAX_HISTORY_LOAD", "20"))  # mensajes a cargar desde BD por sesión

router = APIRouter()


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Hacer una pregunta sobre los documentos",
    response_description="Pregunta, respuesta generada, chunks recuperados y session_id.",
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

    **Historial de chat:**
    - Si envías `session_id`, se carga el historial desde BD y se guarda este turno en esa sesión.
    - Si **no** envías `session_id`, el backend crea una nueva sesión, guarda este turno y devuelve `session_id` en la respuesta; el cliente debe guardarlo y enviarlo en las siguientes peticiones para tener conversación continua.
    - Opcionalmente puedes enviar `history` en el body en lugar de depender de la BD.

    **Respuesta:** Siempre incluye `session_id` (creado por el backend si no lo enviaste), además de `question`, `answer`, `results`, `context_used`.
    """
    if not db.query(Chunk).first():
        raise HTTPException(
            status_code=503,
            detail="No hay documentos indexados. Por favor, suba documentos primero.",
        )

    # session_id: si el cliente no envía, lo creamos aquí y lo devolvemos para que lo use en adelante
    effective_session_id = request.session_id if request.session_id else str(uuid.uuid4())

    # Historial: desde el body o desde BD por session_id
    history_list: list[dict] = []
    if request.history:
        history_list = [{"role": m.role, "content": m.content} for m in request.history]
    elif request.session_id:
        rows = (
            db.execute(
                select(ChatMessage.role, ChatMessage.content)
                .where(ChatMessage.session_id == effective_session_id)
                .order_by(ChatMessage.created_at.asc())
                .limit(MAX_HISTORY_LOAD)
            )
            .fetchall()
        )
        history_list = [{"role": r.role, "content": r.content} for r in rows]

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

    answer = generate_answer(
        question=request.question,
        context=context_for_llm,
        history=history_list if history_list else None,
    )

    # Guardar este turno en BD (siempre; session_id creado por backend si no vino en la petición)
    if db.get(SessionModel, effective_session_id) is None:
        db.add(SessionModel(id=effective_session_id))
        db.flush()
    db.add(ChatMessage(session_id=effective_session_id, role="user", content=request.question))
    db.add(ChatMessage(session_id=effective_session_id, role="assistant", content=answer))
    db.commit()

    return AskResponse(
        question=request.question,
        answer=answer,
        results=results,
        context_used=context_parts,
        session_id=effective_session_id,
    )