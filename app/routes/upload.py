"""
Subida de documentos: múltiples formatos vía DocumentProcessor.

Indexa en BD (documents + chunks con embeddings) para consultas RAG posteriores.
El texto se normaliza (especialmente PDF) para mejorar la calidad en búsqueda semántica.
"""
from typing import List, Optional, Tuple
import logging
import uuid
import asyncio

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.rag.chunking import chunk_text
from app.rag.document_processor import DocumentProcessor
from app.schemas import UploadResponse, UploadedDocument
from app.rag.embeddings import get_embeddings
from app.db.models import Document as DocumentModel, Chunk as ChunkModel, Collection as CollectionModel
from app.db.database import get_db, SessionLocal
from app.dependencies import get_collection_with_access

router = APIRouter()
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = ", ".join(sorted(DocumentProcessor.SUPPORTED_FORMATS))
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_FILES_PER_COLLECTION = 10


def _process_file_with_own_session(
    *,
    filename: str,
    size_bytes: int,
    content: bytes,
    collection_id: Optional[str] = None,
) -> Tuple[Optional[UploadedDocument], Optional[dict]]:
    """
    Procesa un archivo (texto, chunking, embeddings) y lo guarda en BD
    usando su propia sesión de SQLAlchemy. Se ejecuta típicamente en un
    hilo separado vía asyncio.to_thread para habilitar concurrencia.
    """
    db = SessionLocal()
    try:
        text = DocumentProcessor.process_document(content, filename)
        if not text or not text.strip():
            return None, {
                "filename": filename,
                "error": "El documento está vacío o no se pudo extraer texto.",
            }

        chunks = chunk_text(text)
        if not chunks:
            return None, {
                "filename": filename,
                "error": "No se pudo dividir en chunks (texto vacío o demasiado corto).",
            }

        document_id = str(uuid.uuid4())
        document = DocumentModel(
            id=document_id,
            filename=filename,
            size=size_bytes,
            collection_id=collection_id,  # puede ser None en /upload
        )

        chunk_texts = [c.strip() for c in chunks]
        embeddings = get_embeddings(chunk_texts)
        if len(embeddings) != len(chunk_texts):
            raise RuntimeError("Número de embeddings no coincide con número de chunks")

        db.add(document)
        db.flush()

        chunks_models = []
        for i, chunk in enumerate(chunk_texts):
            chunk_id = f"{document_id}_{i}"
            embedding = embeddings[i]
            chunk_model = ChunkModel(
                id=chunk_id,
                document_id=document_id,
                chunk_index=i,
                filename=filename,
                text=chunk,
                embedding=embedding,
            )
            chunks_models.append(chunk_model)

        db.add_all(chunks_models)
        db.commit()

        return UploadedDocument(id=document_id, filename=filename), None

    except ValueError as e:
        db.rollback()
        logger.warning(
            "Error de validación al procesar archivo %s: %s",
            filename,
            e,
        )
        return None, {
            "filename": filename,
            "error": str(e),
        }
    except Exception:
        db.rollback()
        logger.exception("Error interno al procesar archivo %s", filename)
        return None, {
            "filename": filename,
            "error": "Error interno al procesar este archivo. Revisa los logs del servidor para más detalles.",
        }
    finally:
        db.close()



@router.post(
    "/upload/{collection_id}",
    response_model=UploadResponse,
    summary="Subir documentos a una colección específica",
    response_description="Lista de archivos subidos correctamente, fallos (si los hay) y número de documentos indexados.",
)
async def upload_files_to_collection(
    collection: CollectionModel = Depends(get_collection_with_access),
    db: Session = Depends(get_db),
    files: List[UploadFile] = File(
        ...,
        description=f"Uno o más archivos a procesar. Formatos soportados: {SUPPORTED_EXTENSIONS}.",
    ),
):
    """
    Procesa y **indexa** uno o más documentos en una colección específica.
    
    Para colecciones públicas: no requiere token.
    Para colecciones privadas: requiere token obtenido con POST /collections/{id}/unlock.
    
    Header opcional (requerido para privadas):
        Authorization: Bearer <access_token>
    
    Flujo idéntico al endpoint /upload pero guardando con collection_id.
    """
    collection_id = collection.id

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    uploaded_files: List[UploadedDocument] = []
    failed_files: List[dict] = []

    # Contar cuántos documentos existen ya en la colección para respetar el límite.
    existing_docs_count = (
        db.query(DocumentModel)
        .filter(DocumentModel.collection_id == collection_id)
        .count()
    )
    slots_left = max(0, MAX_FILES_PER_COLLECTION - existing_docs_count)

    # Validamos y leemos el contenido de los archivos; luego procesamos en paralelo.
    tasks = []
    for file in files:
        if not file.filename or not file.filename.strip():
            failed_files.append({"filename": "(sin nombre)", "error": "Nombre de archivo vacío."})
            continue

        if not DocumentProcessor.is_supported(file.filename):
            failed_files.append({
                "filename": file.filename,
                "error": f"Formato no soportado. Use: {SUPPORTED_EXTENSIONS}",
            })
            continue

        # Límite máximo de documentos por colección.
        if slots_left <= 0:
            failed_files.append({
                "filename": file.filename,
                "error": f"Límite de {MAX_FILES_PER_COLLECTION} documentos por colección alcanzado.",
            })
            continue

        content = await file.read()
        size_bytes = getattr(file, "size", None) or len(content)

        # Validar tamaño máximo por archivo (10 MB).
        if size_bytes > MAX_FILE_SIZE_BYTES:
            failed_files.append({
                "filename": file.filename,
                "error": f"El archivo supera el tamaño máximo permitido de {MAX_FILE_SIZE_MB} MB.",
            })
            continue

        slots_left -= 1

        tasks.append(
            asyncio.to_thread(
                _process_file_with_own_session,
                filename=file.filename,
                size_bytes=size_bytes,
                content=content,
                collection_id=collection_id,
            )
        )

    if tasks:
        results = await asyncio.gather(*tasks)
        for uploaded, failed in results:
            if uploaded is not None:
                uploaded_files.append(uploaded)
            if failed is not None:
                failed_files.append(failed)

    if not uploaded_files:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "No se pudo procesar ningún archivo. Formatos soportados: " + SUPPORTED_EXTENSIONS,
                "failed_files": failed_files,
            },
        )

    return UploadResponse(
        files_uploaded=uploaded_files,
        failed_files=failed_files,
        documents_indexed=len(uploaded_files),
    )










@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Subir documentos para indexar",
    response_description="Lista de archivos subidos correctamente, fallos (si los hay) y número de documentos indexados.",
)
async def upload_files(
    db: Session = Depends(get_db),
    files: List[UploadFile] = File(
        ...,
        description=f"Uno o más archivos a procesar. Formatos soportados: {SUPPORTED_EXTENSIONS}.",
    ),
):
    """
    Procesa y **indexa** uno o más documentos para poder consultarlos luego con `POST /api/ask`.

    Flujo por cada archivo:
    1. Valida nombre y extensión (solo formatos soportados).
    2. Extrae el texto según el tipo (PDF, DOCX, XLSX, etc.) y lo normaliza.
    3. Divide el texto en chunks (RecursiveCharacterTextSplitter).
    4. Crea el índice FAISS con embeddings (o añade al existente) y guarda metadata en memoria.

    **Formatos soportados:** .txt, .pdf, .docx, .md, .csv, .xlsx, .xls

    Si algún archivo falla (formato no soportado, vacío, error de lectura), se incluye en
    `failed_files` con el motivo; el resto se procesa igual. Si **todos** fallan, responde 400.

    **Respuesta:**
    - `files_uploaded`: lista de { id, filename } de los documentos indexados correctamente.
    - `failed_files`: lista de { filename, error } para los que fallaron.
    - `documents_indexed`: cantidad de documentos indexados (= len(files_uploaded)).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    uploaded_files: List[UploadedDocument] = []
    failed_files: List[dict] = []

    tasks = []
    for file in files:
        if not file.filename or not file.filename.strip():
            failed_files.append({"filename": "(sin nombre)", "error": "Nombre de archivo vacío."})
            continue

        if not DocumentProcessor.is_supported(file.filename):
            failed_files.append({
                "filename": file.filename,
                "error": f"Formato no soportado. Use: {SUPPORTED_EXTENSIONS}",
            })
            continue

        content = await file.read()
        size_bytes = getattr(file, "size", None) or len(content)

        # Validar tamaño máximo por archivo (10 MB).
        if size_bytes > MAX_FILE_SIZE_BYTES:
            failed_files.append({
                "filename": file.filename,
                "error": f"El archivo supera el tamaño máximo permitido de {MAX_FILE_SIZE_MB} MB.",
            })
            continue

        tasks.append(
            asyncio.to_thread(
                _process_file_with_own_session,
                filename=file.filename,
                size_bytes=size_bytes,
                content=content,
                collection_id=None,
            )
        )

    if tasks:
        results = await asyncio.gather(*tasks)
        for uploaded, failed in results:
            if uploaded is not None:
                uploaded_files.append(uploaded)
            if failed is not None:
                failed_files.append(failed)

    if not uploaded_files:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "No se pudo procesar ningún archivo. Formatos soportados: " + SUPPORTED_EXTENSIONS,
                "failed_files": failed_files,
            },
        )

    return UploadResponse(
        files_uploaded=uploaded_files,
        failed_files=failed_files,
        documents_indexed=len(uploaded_files),
    )