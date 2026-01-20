from fastapi import APIRouter, UploadFile, File, HTTPException
from app.rag.chunking import chunk_text
from app.rag.embeddings import get_embedding
from app.rag.faiss_index import init_index, add_embeddings, is_initialized
from app.rag.store import CHUNKS_METADATA, CHUNK_IDS
from app.schemas import UploadResponse
from typing import List
import numpy as np
import uuid

router = APIRouter()

@router.post("/upload", response_model=UploadResponse)
async def upload_files(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    uploaded_files = []
    failed_files = []

    for file in files:
        if not file.filename.endswith('.txt'):
            failed_files.append({
                "filename": file.filename,
                "error": "Only .txt files are supported for now."
            })
            continue
        
        try:
            content = await file.read()
            text = content.decode('utf-8')

            chunks = chunk_text(text)
            if not chunks:
                failed_files.append({
                    "filename": file.filename,
                    "error": "File is empty or could not be chunked."
                })
                continue
            
            document_id = str(uuid.uuid4())
            embeddings = []

            for i, chunk in enumerate(chunks):
                embedding = get_embedding(chunk)
                embeddings.append(embedding)
                chunk_id = f"{document_id}_{i}"
                CHUNK_IDS.append(chunk_id)
                CHUNKS_METADATA[chunk_id] = {
                    "document_id": document_id,
                    "chunk_index": i,
                    "text": chunk
                }

            embeddings = np.array(embeddings).astype("float32")
        
            if not is_initialized():
                init_index(embeddings.shape[1])
            
            add_embeddings(embeddings)
            
            uploaded_files.append(file.filename)

        except Exception as e:
            failed_files.append({
                "filename": file.filename,
                "error": str(e)
            })

    if not uploaded_files:
        raise HTTPException(
            status_code=400,
            detail="No files could be processed"
        )
    
    return {
        "files_uploaded": uploaded_files,
        "failed_files": failed_files,
        "documents_indexed": len(uploaded_files)
    }