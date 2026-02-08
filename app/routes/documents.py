"""
Endpoints para listar y consultar documentos indexados.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, Chunk

router = APIRouter()


@router.get(
    "/documents",
    summary="Listar documentos indexados",
    response_description="Lista de documentos con id, nombre y cantidad de chunks.",
)
def list_documents(db: Session = Depends(get_db)):
    """
    Devuelve todos los documentos indexados en la BD.

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
    stmt = (
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
    rows = db.execute(stmt).fetchall()
    print(rows)

    return [
        {
            "id": row.id,
            "filename": row.filename,
            "size": row.size,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "chunk_count": row.chunk_count or 0,
        }
        for row in rows
    ]


@router.get(
    "/documents/{document_id}/text",
    summary="Obtener el texto completo de un documento",
    response_description="Texto concatenado de todos los chunks del documento.",
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

    return {
        "document_id": document_id,
        "filename": doc.filename,
        "text": full_text,
    }
