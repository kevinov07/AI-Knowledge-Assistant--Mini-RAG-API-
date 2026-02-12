from sqlalchemy import select
from langchain_core.documents import Document

from app.db.models import Chunk, Document as DocumentModel


def similarity_search_chunks_pgvector(
    session,
    question: str,
    k: int = 5,
    get_embedding=None,
    collection_id: str | None = None,
):
    """
    Equivalente a similarity_search_with_score de FAISS usando pgvector.

    Usa el ORM de SQLAlchemy y Chunk.embedding.l2_distance() (pgvector) para
    ordenar por distancia L2 y devolver (Document, score). Menor distancia = más similar.

    Args:
        session: Sesión SQLAlchemy (con register_vector en la conexión).
        question: Texto de la pregunta.
        k: Número máximo de chunks a devolver.
        get_embedding: Función (str) -> list[float]. Si no se pasa, se usa app.rag.embeddings.get_embedding.
        collection_id: ID de colección opcional. Si se provee, filtra solo chunks de esa colección.

    Returns:
        Lista de tuplas (Document, score), donde Document tiene page_content y metadata
        (document_id, chunk_index, filename); score es float (distancia L2).
    """
    if get_embedding is None:
        from app.rag.embeddings import get_embedding as _ge
        get_embedding = _ge
    query_embedding = get_embedding(question)

    distance_col = Chunk.embedding.l2_distance(query_embedding)
    stmt = (
        select(
            Chunk.document_id,
            Chunk.chunk_index,
            Chunk.text,
            Chunk.filename,
            distance_col.label("distance"),
        )
        .order_by(distance_col)
        .limit(k)
    )
    
    # Filtrar por colección si se provee
    if collection_id:
        stmt = stmt.join(DocumentModel, Chunk.document_id == DocumentModel.id).where(
            DocumentModel.collection_id == collection_id
        )
    
    rows = session.execute(stmt).fetchall()

    out = []
    for row in rows:
        doc = Document(
            page_content=row.text,
            metadata={
                "document_id": row.document_id,
                "chunk_index": row.chunk_index,
                "filename": row.filename,
            },
        )
        out.append((doc, float(row.distance)))
    return out


def get_context_chunks_from_db(
    session,
    document_id: str,
    center_index: int,
    window: int = 1,
) -> list[str]:
    """
    Recupera textos de chunks vecinos de un documento desde la BD (para expansión de contexto).

    Equivalente a get_context_chunks pero leyendo de la tabla chunks vía ORM.
    """
    lo = center_index - window
    hi = center_index + window
    stmt = (
        select(Chunk.text)
        .where(
            Chunk.document_id == document_id,
            Chunk.chunk_index.between(lo, hi),
        )
        .order_by(Chunk.chunk_index)
    )
    return list(session.scalars(stmt))


def get_context_chunks(
    chunks_metadata: dict,
    document_id: str,
    center_index: int,
    window: int = 1
) -> list[str]:
    """
    Recupera chunks vecinos de un documento para expandir el contexto alrededor de un chunk central.
    
    Útil para no cortar ideas a mitad: si recuperas el chunk 3 por similitud, también obtienes
    los chunks 1, 2, 4, 5 (con window=2) para tener contexto completo.
    
    Args:
        chunks_metadata: Diccionario con metadata de todos los chunks (chunk_id -> {document_id, chunk_index, text, ...}).
        document_id: ID del documento del cual recuperar chunks.
        center_index: Índice del chunk central (el recuperado por similitud).
        window: Radio de expansión. Con window=2, recupera chunks desde (center_index - 2) hasta (center_index + 2).
    
    Returns:
        Lista de textos de chunks ordenados por chunk_index (del mismo documento, dentro del rango).
    """
    relevant = []

    for chunk_id, data in chunks_metadata.items():
        if data["document_id"] != document_id:
            continue

        if abs(data["chunk_index"] - center_index) <= window:
            relevant.append(data)

    relevant.sort(key=lambda c: c["chunk_index"])

    return [c["text"] for c in relevant]
