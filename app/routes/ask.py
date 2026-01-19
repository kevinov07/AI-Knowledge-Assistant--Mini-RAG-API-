from fastapi import APIRouter, HTTPException
from app.llm.groq_client import generate_answer
from app.schemas import QuestionRequest
from app.rag.faiss_index import search_embeddings, is_initialized
from app.rag.embeddings import get_embedding
from app.rag.retriever import get_context_chunks
from app.rag.store import CHUNKS_METADATA, CHUNK_IDS
import numpy as np


router = APIRouter()


@router.post("/ask")
async def ask_question(request: QuestionRequest):
  if not is_initialized():
     return {"error": "El índice FAISS no está inicializado. Por favor, suba documentos primero."}
 
  query_embedding = np.array(
      [get_embedding(request.question)],
      dtype="float32"
  )

  scores, indices = search_embeddings(query_embedding, k=request.k)

  results = []
  all_context_chunks = []
  
  for idx, score in zip(indices[0], scores[0]):
    if idx == -1:
      continue

    chunk_id = CHUNK_IDS[idx]
    chunk_data = CHUNKS_METADATA[chunk_id]

    context_chunks = get_context_chunks(
        CHUNKS_METADATA,
        chunk_data["document_id"],
        chunk_data["chunk_index"],
        window=1
    )

    all_context_chunks.extend(context_chunks)


    results.append({
      "text": chunk_data["text"],
      "document_id": chunk_data["document_id"],
      "chunk_index": chunk_data["chunk_index"],
      "score": float(score),
    })
  
  context_for_llm = "\n---\n".join(dict.fromkeys(all_context_chunks))

  answer = generate_answer(
    question=request.question, 
    context=context_for_llm
  )

  return {
      "question": request.question,
      "answer": answer,
      "results": results
  }