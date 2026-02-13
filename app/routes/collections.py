from fastapi import APIRouter, Depends, HTTPException, Query
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
    DeleteDocumentsRequest,
    DeleteDocumentsResponse,
    PaginatedCollectionResponse,
    PaginatedDocumentResponse,
    PaginatedMessageResponse,
    PaginationMeta,
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
    response_model=PaginatedCollectionResponse,
    response_model_exclude_none=True,
    summary="Obtener colecciones (paginado)",
    response_description="Listado paginado de colecciones con conteo de documentos y mensajes.",
)
def get_collections(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Página (1-based)."),
    page_size: int = Query(10, ge=1, le=100, description="Elementos por página."),
):
    # Subconsultas para contar documentos y mensajes por colección
    doc_count_subq = (
        select(DocumentModel.collection_id, func.count(DocumentModel.id).label("doc_count"))
        .group_by(DocumentModel.collection_id)
        .subquery()
    )
    msg_count_subq = (
        select(SessionModel.collection_id, func.count(ChatMessageModel.id).label("msg_count"))
        .join(ChatMessageModel, ChatMessageModel.session_id == SessionModel.id)
        .group_by(SessionModel.collection_id)
        .subquery()
    )
    base_stmt = (
        select(
            CollectionModel,
            func.coalesce(doc_count_subq.c.doc_count, 0).label("document_count"),
            func.coalesce(msg_count_subq.c.msg_count, 0).label("message_count"),
        )
        .outerjoin(doc_count_subq, CollectionModel.id == doc_count_subq.c.collection_id)
        .outerjoin(msg_count_subq, CollectionModel.id == msg_count_subq.c.collection_id)
        .order_by(CollectionModel.created_at.desc())
    )
    # Contar total
    count_stmt = select(func.count()).select_from(CollectionModel)
    total = db.execute(count_stmt).scalar_one()
    total_pages = max(1, (total + page_size - 1) // page_size)
    # Paginar
    offset = (page - 1) * page_size
    stmt = base_stmt.offset(offset).limit(page_size)
    rows = db.execute(stmt).fetchall()
    items = [
        CollectionResponse(
            id=row[0].id,
            name=row[0].name,
            description=row[0].description,
            is_public=row[0].is_public,
            created_at=row[0].created_at.isoformat() if row[0].created_at else None,
            document_count=int(row.document_count),
            message_count=int(row.message_count),
        )
        for row in rows
    ]
    return PaginatedCollectionResponse(
        items=items,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )



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
        document_count=0,
        message_count=0,
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


@router.delete(
    "/collections/{collection_id}",
    summary="Eliminar una colección",
    response_description="Colección eliminada (incluye documentos, chunks, sesión y mensajes).",
)
def delete_collection(
    collection: CollectionModel = Depends(get_collection_with_access),
    db: Session = Depends(get_db),
):
    """
    Elimina una colección y todos sus recursos asociados por CASCADE:
    - Documentos
    - Chunks
    - Sesión de chat
    - Mensajes
    
    Para colecciones públicas: no requiere token.
    Para colecciones privadas: requiere token obtenido con POST /collections/{id}/unlock.
    """
    db.delete(collection)
    db.commit()
    return {"deleted": True}


@router.get(
    "/collections/{collection_id}/documents",
    response_model=PaginatedDocumentResponse,
    summary="Listar documentos de una colección (paginado)",
    response_description="Lista paginada de documentos con id, nombre, tamaño y cantidad de chunks.",
)
def get_collection_documents(
    collection: CollectionModel = Depends(get_collection_with_access),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Página (1-based)."),
    page_size: int = Query(10, ge=1, le=100, description="Elementos por página."),
):
    """
    Devuelve documentos indexados en esta colección (paginado).
    
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
    base_stmt = (
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
    total = db.execute(select(func.count()).select_from(DocumentModel).where(DocumentModel.collection_id == collection_id)).scalar_one()
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    rows = db.execute(base_stmt.offset(offset).limit(page_size)).fetchall()
    items = [
        DocumentListItem(
            id=row.id,
            filename=row.filename,
            size=row.size,
            created_at=row.created_at.isoformat() if row.created_at else None,
            chunk_count=row.chunk_count or 0,
        )
        for row in rows
    ]
    return PaginatedDocumentResponse(
        items=items,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.delete(
    "/collections/{collection_id}/documents",
    response_model=DeleteDocumentsResponse,
    summary="Eliminar varios documentos de una colección",
    response_description="Cantidad e IDs de documentos eliminados.",
)
def delete_collection_documents(
    payload: DeleteDocumentsRequest,
    collection: CollectionModel = Depends(get_collection_with_access),
    db: Session = Depends(get_db),
):
    """
    Elimina uno o más documentos de una colección.
    Solo se eliminan documentos que pertenecen a esta colección (los demás se ignoran).
    
    Los chunks se eliminan automáticamente por CASCADE.
    
    Para colecciones públicas: no requiere token.
    Para colecciones privadas: requiere token obtenido con POST /collections/{id}/unlock.
    """
    collection_id = collection.id
    deleted_ids: list[str] = []
    
    for doc_id in payload.document_ids:
        doc = db.get(DocumentModel, doc_id)
        if doc and doc.collection_id == collection_id:
            db.delete(doc)
            deleted_ids.append(doc_id)
    
    db.commit()
    
    return DeleteDocumentsResponse(
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.get(
    "/collections/{collection_id}/messages",
    response_model=PaginatedMessageResponse,
    summary="Obtener mensajes del chat de una colección (paginado)",
    response_description="Lista paginada de mensajes ordenados cronológicamente.",
)
def get_collection_messages(
    collection: CollectionModel = Depends(get_collection_with_access),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Página (1-based)."),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página."),
):
    """
    Devuelve el historial de mensajes del chat de esta colección (paginado).
    
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
        return PaginatedMessageResponse(
            items=[],
            pagination=PaginationMeta(page=1, page_size=page_size, total=0, total_pages=0),
        )
    
    total = db.execute(
        select(func.count()).select_from(ChatMessageModel).where(ChatMessageModel.session_id == session.id)
    ).scalar_one()
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    messages = db.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == session.id)
        .order_by(ChatMessageModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    ).scalars().all()
    
    items = [
        ChatMessageSchema(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at.isoformat() if msg.created_at else None,
        )
        for msg in messages
    ]
    return PaginatedMessageResponse(
        items=items,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


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
