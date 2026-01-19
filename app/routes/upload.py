from fastapi import APIRouter, UploadFile as Up, File
from app.rag.chunking import chunk_text
from app.rag.embeddings import get_embedding
from app.rag.faiss_index import init_index, add_embeddings, is_initialized
from app.rag.store import CHUNKS_METADATA, CHUNK_IDS
import numpy as np
import uuid

router = APIRouter()

@router.post("/upload")
async def upload_file(file: Up):
    if not file.filename.endswith('.txt'):
        return {"error": "Only .txt files are supported for now."}
    
    content = await file.read()
    text = content.decode('utf-8')
    chunks = chunk_text(text)
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
      
    if len(embeddings) > 0:
        if not is_initialized():
          init_index(embeddings.shape[1])
        
        add_embeddings(embeddings)

    return {
        "status": "ok",
        "document_id": document_id,
        "num_chunks": len(chunks)
    }