
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import health, text, ask, upload
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="AI Knowledge Assistant",
    description="Mini RAG API para consultas sobre documentos",
    version="0.1.0"
)

# Configurar CORS para permitir peticiones desde el frontend Angular
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # URL del frontend Angular
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers con prefijo /api
app.include_router(health.router, prefix="/api")
app.include_router(text.router, prefix="/api")
app.include_router(ask.router, prefix="/api")
app.include_router(upload.router, prefix="/api")