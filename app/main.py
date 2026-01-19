
from fastapi import FastAPI
from app.routes import health, text, ask, upload
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="AI Knowledge Assistant",
    description="Mini RAG API para consultas sobre documentos",
    version="0.1.0"
)

app.include_router(health.router)
app.include_router(text.router)
app.include_router(ask.router)
app.include_router(upload.router)