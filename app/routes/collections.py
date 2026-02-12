from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.utils.code_hash import hash_code, verify_code
from app.utils.token import create_collection_access_token, ACCESS_TOKEN_EXPIRE_HOURS
from app.dependencies import get_collection_with_access

from app.schemas import (
    CollectionCreate,
    CollectionResponse,
    UnlockCollectionRequest,
    UnlockCollectionResponse,
    DocumentListItem,
    ChatMessage as ChatMessageSchema,
    QuestionRequest,
    AskResponse,
    AskResultItem,
)
from app.db.models import (
    Collection as CollectionModel,
    Session as SessionModel,
    Document as DocumentModel,
    Chunk as ChunkModel,
    ChatMessage as ChatMessageModel,
)
from app.llm.groq_client import generate_answer
from app.rag.embeddings import get_embedding
from app.rag.retriever import similarity_search_chunks_pgvector, get_context_chunks_from_db
import os
import uuid


router = APIRouter()

@router.get(
    "/collections",
    response_model=list[CollectionResponse],
    response_model_exclude_none=True,
    summary="Obtener todas las colecciones",
    response_description="Listado de colecciones (el código nunca se devuelve).",
)
def get_collections(db: Session = Depends(get_db)):
    stmt = select(CollectionModel).order_by(CollectionModel.created_at.desc())
    rows = db.execute(stmt).scalars().all()
    return [
        CollectionResponse(
            id=row.id,
            name=row.name,
            description=row.description,
            is_public=row.is_public,
        )
        for row in rows
    ]



@router.post(
    "/collections",
    response_model=CollectionResponse,
    response_model_exclude_none=True,
    summary="Crear una colección",
    response_description="Colección creada (el código no se devuelve; se guarda hasheado).",
)
def create_collection(collection: CollectionCreate, db: Session = Depends(get_db)):
    code_hash = hash_code(collection.code) if collection.code else None
    print(f"[create_collection] Original code: '{collection.code}', Hash: '{code_hash}'")
    collection_model = CollectionModel(
        name=collection.name,
        description=collection.description,
        is_public=collection.is_public,
        code=code_hash,
    )
    db.add(collection_model)
    db.flush()
    db.add(SessionModel(collection_id=collection_model.id))
    db.commit()

    return CollectionResponse(
        id=collection_model.id,
        name=collection_model.name,
        description=collection_model.description,
        is_public=collection_model.is_public,
    )

@router.post(
    "/collections/{collection_id}/unlock",
    response_model=UnlockCollectionResponse,
    summary="Desbloquear una colección",
    response_description="Token de acceso temporal para la colección.",
)
def unlock_collection(
    collection_id: str,
    payload: UnlockCollectionRequest,
    db: Session = Depends(get_db),
):
    collection = db.get(CollectionModel, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Colección no encontrada")

    if not collection.is_public:
        if not payload.code or not payload.code.strip():
            raise HTTPException(status_code=400, detail="Código de acceso requerido")
        verified = verify_code(payload.code, collection.code)
        if not verified:
            raise HTTPException(status_code=401, detail="Código de acceso incorrecto")

    # Generar token de acceso temporal
    access_token = create_collection_access_token(collection_id)
    
    return UnlockCollectionResponse(
        unlocked=True,
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600,  # en segundos
    )


@router.get(
    "/collections/{collection_id}/documents",
    response_model=list[DocumentListItem],
    summary="Listar documentos de una colección",
    response_description="Lista de documentos con id, nombre, tamaño y cantidad de chunks.",
)
def get_collection_documents(
    collection: CollectionModel = Depends(get_collection_with_access),
    db: Session = Depends(get_db),
):
    """
    Devuelve todos los documentos indexados en esta colección.
    
    Para colecciones públicas: no requiere token.
    Para colecciones privadas: requiere token obtenido con POST /collections/{id}/unlock.
    """
    collection_id = collection.id
    
    # Contar chunks por documento
    chunk_count_subq = (
        select(ChunkModel.document_id, func.count(ChunkModel.id).label("chunk_count"))
        .group_by(ChunkModel.document_id)
        .subquery()
    )
    stmt = (
        select(
            DocumentModel.id,
            DocumentModel.filename,
            DocumentModel.created_at,
            chunk_count_subq.c.chunk_count,
            DocumentModel.size,
        )
        .outerjoin(chunk_count_subq, DocumentModel.id == chunk_count_subq.c.document_id)
        .where(DocumentModel.collection_id == collection_id)
        .order_by(DocumentModel.created_at.desc())
    )
    rows = db.execute(stmt).fetchall()
    return [
        DocumentListItem(
            id=row.id,
            filename=row.filename,
            size=row.size,
            created_at=row.created_at.isoformat() if row.created_at else None,
            chunk_count=row.chunk_count or 0,
        )
        for row in rows
    ]


@router.get(
    "/collections/{collection_id}/messages",
    response_model=list[ChatMessageSchema],
    summary="Obtener mensajes del chat de una colección",
    response_description="Lista de mensajes ordenados cronológicamente.",
)
def get_collection_messages(
    collection: CollectionModel = Depends(get_collection_with_access),
    db: Session = Depends(get_db),
):
    """
    Devuelve el historial de mensajes del chat de esta colección.
    
    Como cada colección tiene una sesión asociada (1:1), devuelve los mensajes
    de esa sesión ordenados por fecha de creación.
    
    Para colecciones públicas: no requiere token.
    Para colecciones privadas: requiere token obtenido con POST /collections/{id}/unlock.
    """
    collection_id = collection.id
    
    # Obtener la sesión de esta colección (relación 1:1)
    session = db.execute(
        select(SessionModel).where(SessionModel.collection_id == collection_id)
    ).scalar_one_or_none()
    
    if not session:
        return []  # No hay sesión aún, devolver lista vacía
    
    # Obtener mensajes de la sesión
    messages = db.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == session.id)
        .order_by(ChatMessageModel.created_at.asc())
    ).scalars().all()
    
    return [
        ChatMessageSchema(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at.isoformat() if msg.created_at else None,
        )
        for msg in messages
    ]


MAX_CONTEXT_CHARS = int(os.getenv("GROQ_MAX_CONTEXT_CHARS", "32000"))


@router.post(
    "/collections/{collection_id}/ask",
    response_model=AskResponse,
    summary="Hacer una pregunta sobre los documentos de una colección",
    response_description="Pregunta, respuesta generada, chunks recuperados.",
)
async def ask_collection_question(
    request: QuestionRequest,
    collection: CollectionModel = Depends(get_collection_with_access),
    db: Session = Depends(get_db),
):
    """
    Responde una pregunta usando búsqueda semántica **solo sobre los documentos de esta colección**.
    
    Flujo idéntico a POST /ask pero filtrando chunks por collection_id.
    El historial se guarda en la sesión asociada a esta colección.
    
    Para colecciones públicas: no requiere token.
    Para colecciones privadas: requiere token obtenido con POST /collections/{id}/unlock.
    """
    collection_id = collection.id
    
    # Verificar que hay documentos en esta colección
    has_docs = db.execute(
        select(ChunkModel.id)
        .join(DocumentModel, ChunkModel.document_id == DocumentModel.id)
        .where(DocumentModel.collection_id == collection_id)
        .limit(1)
    ).first()
    
    if not has_docs:
        raise HTTPException(
            status_code=503,
            detail="No hay documentos indexados en esta colección. Por favor, suba documentos primero.",
        )
    
    # Obtener la sesión de esta colección
    session = db.execute(
        select(SessionModel).where(SessionModel.collection_id == collection_id)
    ).scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=500, detail="La colección no tiene sesión asociada.")
    
    effective_session_id = session.id
    
    # Historial desde BD (siempre usar la sesión de la colección)
    history_list: list[dict] = []
    if not request.history:
        rows = db.execute(
            select(ChatMessageModel.role, ChatMessageModel.content)
            .where(ChatMessageModel.session_id == effective_session_id)
            .order_by(ChatMessageModel.created_at.asc())
            .limit(20)
        ).fetchall()
        history_list = [{"role": r.role, "content": r.content} for r in rows]
    else:
        history_list = [{"role": m.role, "content": m.content} for m in request.history]
    
    # Búsqueda semántica SOLO en chunks de esta colección
    docs_with_scores = similarity_search_chunks_pgvector(
        db, request.question, k=request.k, get_embedding=get_embedding, collection_id=collection_id
    )
    
    if not docs_with_scores:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron resultados relevantes en esta colección.",
        )
    
    # Expandir contexto con vecinos
    results = []
    all_context_chunks = []
    
    for doc, score in docs_with_scores:
        meta = doc.metadata
        document_id = meta.get("document_id", "")
        chunk_index = meta.get("chunk_index", 0)
        chunk_text = doc.page_content
        
        # Expansión de contexto desde la BD (chunks vecinos ±2)
        context_chunks = get_context_chunks_from_db(db, document_id, chunk_index, window=2)
        all_context_chunks.extend(context_chunks)
        
        results.append({
            "text": chunk_text,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "score": float(score),
        })
    
    context_texts = all_context_chunks
    context_str = "\n\n".join(context_texts)
    
    # Truncar si es muy largo
    if len(context_str) > MAX_CONTEXT_CHARS:
        context_str = context_str[:MAX_CONTEXT_CHARS] + "\n[... contexto truncado ...]"
        context_texts = [context_str]
    
    # Generar respuesta con LLM
    answer = generate_answer(request.question, context_str, history_list)
    
    # Guardar pregunta y respuesta en BD
    user_msg = ChatMessageModel(
        session_id=effective_session_id,
        role="user",
        content=request.question,
    )
    assistant_msg = ChatMessageModel(
        session_id=effective_session_id,
        role="assistant",
        content=answer,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    db.commit()
    
    return AskResponse(
        question=request.question,
        answer=answer,
        results=[
            AskResultItem(
                text=r["text"],
                document_id=r["document_id"],
                chunk_index=r["chunk_index"],
                score=r["score"],
            )
            for r in results
        ],
        context_used=context_texts,
        session_id=effective_session_id,
    )
