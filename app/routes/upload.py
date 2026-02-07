"""
Subida de documentos: múltiples formatos vía DocumentProcessor.

Indexa en BD (documents + chunks con embeddings) para consultas RAG posteriores.
El texto se normaliza (especialmente PDF) para mejorar la calidad en búsqueda semántica.
"""
from typing import List
import logging
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.rag.chunking import chunk_text
from app.rag.document_processor import DocumentProcessor
from app.schemas import UploadResponse
from app.rag.embeddings import get_embeddings
from app.db.models import Document as DocumentModel, Chunk as ChunkModel
from app.db.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = ", ".join(sorted(DocumentProcessor.SUPPORTED_FORMATS))


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
    - `files_uploaded`: nombres de los archivos indexados correctamente.
    - `failed_files`: lista de { filename, error } para los que fallaron.
    - `documents_indexed`: cantidad de documentos indexados (= len(files_uploaded)).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    uploaded_files = []
    failed_files = []

    for file in files:
        if not file.filename or not file.filename.strip():
            failed_files.append({"filename": "(sin nombre)", "error": "Nombre de archivo vacío."})
            continue

        if not DocumentProcessor.is_supported(file.filename):
            failed_files.append({
                "filename": file.filename,
                "error": f"Formato no soportado. Use: {SUPPORTED_EXTENSIONS}"
            })
            continue

        try:
            content = await file.read()
            text = DocumentProcessor.process_document(content, file.filename)
            if not text or not text.strip():
                failed_files.append({
                    "filename": file.filename,
                    "error": "El documento está vacío o no se pudo extraer texto."
                })
                continue

            chunks = chunk_text(text)
            if not chunks:
                failed_files.append({
                    "filename": file.filename,
                    "error": "No se pudo dividir en chunks (texto vacío o demasiado corto)."
                })
                continue

            # document_id = str(uuid.uuid4())
            # documents = [
            #     Document(
            #         page_content=chunk.strip(), 
            #         metadata={
            #             "source": file.filename,
            #             "document_id": document_id,
            #             "chunk_id": f"{document_id}_{i}",
            #             "chunk_index": i,
            #             "filename": file.filename
            #         }
            #     )
            #     for i, chunk in enumerate(chunks)
            # ]

            document_id = str(uuid.uuid4())
            document = DocumentModel(
                id=document_id,
                filename=file.filename,
            )
            # Embeddings en batch (más eficiente que chunk por chunk)
            chunk_texts = [c.strip() for c in chunks]
            embeddings = get_embeddings(chunk_texts)
            if len(embeddings) != len(chunk_texts):
                raise RuntimeError("Número de embeddings no coincide con número de chunks")

            db.add(document)
            db.flush()
            
            # if not is_initialized():
            #     init_vectorstore(documents, get_langchain_embeddings())
            # else:
            #     add_documents(documents)
            chunks_models = []
            for i, chunk in enumerate(chunk_texts):
                chunk_id = f"{document_id}_{i}"

                # CHUNK_IDS.append(chunk_id)
                # CHUNKS_METADATA[chunk_id] = {
                #     "document_id": document_id,
                #     "chunk_index": i,
                #     "text": chunk.strip(),
                #     "filename": file.filename,
                # }
                embedding = embeddings[i]
                chunk_model = ChunkModel(
                    id=chunk_id,
                    document_id=document_id,
                    chunk_index=i,
                    filename=file.filename,
                    text=chunk,
                    embedding=embedding,
                )
                chunks_models.append(chunk_model)
            db.add_all(chunks_models)
            # Commit por archivo: si este archivo va bien, se persiste aunque el siguiente falle.
            db.commit()
            uploaded_files.append(file.filename)

        except ValueError as e:
            # Errores de validación/control (texto vacío, chunks, etc.)
            db.rollback()
            logger.warning(
                "Error de validación al procesar archivo %s: %s",
                file.filename,
                e,
            )
            failed_files.append({
                "filename": file.filename,
                "error": str(e),
            })
        except Exception as e:
            # Errores inesperados (BD, red, etc.). No exponer detalle al cliente.
            db.rollback()
            logger.exception("Error interno al procesar archivo %s", file.filename)
            failed_files.append({
                "filename": file.filename,
                "error": "Error interno al procesar este archivo. Revisa los logs del servidor para más detalles.",
            })

    if not uploaded_files:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "No se pudo procesar ningún archivo. Formatos soportados: " + SUPPORTED_EXTENSIONS,
                "failed_files": failed_files,
            },
        )

    return {
        "files_uploaded": uploaded_files,
        "failed_files": failed_files,
        "documents_indexed": len(uploaded_files)
    }