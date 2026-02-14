"""
Endpoints para listar y consultar documentos indexados.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, Chunk
from app.schemas import DocumentListItem, DocumentTextResponse, PaginatedDocumentResponse, PaginationMeta

router = APIRouter()


@router.get(
    "/documents",
    response_model=PaginatedDocumentResponse,
    summary="Listar documentos indexados (paginado)",
    response_description="Lista paginada de documentos con id, nombre, tamaño y cantidad de chunks.",
)
def list_documents(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Página (1-based)."),
    page_size: int = Query(10, ge=1, le=100, description="Elementos por página."),
):
    """
    Devuelve documentos indexados en la BD (paginado).

    Cada documento incluye:
    - **id**: identificador único.
    - **filename**: nombre del archivo.
    - **created_at**: fecha de subida.
    - **chunk_count**: número de chunks (indica tamaño relativo del documento; no es peso en bytes).
    """
    # Contar chunks por documento en una subconsulta
    chunk_count_subq = (
        select(Chunk.document_id, func.count(Chunk.id).label("chunk_count"))
        .group_by(Chunk.document_id)
        .subquery()
    )
    base_stmt = (
        select(
            Document.id,
            Document.filename,
            Document.created_at,
            chunk_count_subq.c.chunk_count,
            Document.size,
        )
        .outerjoin(chunk_count_subq, Document.id == chunk_count_subq.c.document_id)
        .order_by(Document.created_at.desc())
    )
    total = db.execute(select(func.count()).select_from(Document)).scalar_one()
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


@router.get(
    "/documents/{document_id}/text",
    response_model=DocumentTextResponse,
    summary="Obtener el texto completo de un documento",
    response_description="Documento con texto concatenado de todos los chunks.",
)
def get_document_text(document_id: str, db: Session = Depends(get_db)):
    """
    Devuelve el texto completo del documento (todos sus chunks concatenados en orden).

    Útil para que el frontend muestre el contenido como texto o permita copiar/descargar.
    No devuelve el archivo original (PDF, DOCX, etc.); solo el texto ya extraído e indexado.
    """
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    rows = db.execute(
        select(Chunk.text)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
    ).fetchall()
    parts = [row[0] for row in rows]
    full_text = "\n\n".join(parts) if parts else ""

    return DocumentTextResponse(
        document_id=document_id,
        filename=doc.filename,
        text=full_text,
    )
