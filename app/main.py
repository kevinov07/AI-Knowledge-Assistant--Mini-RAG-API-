import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.database import init_db, engine
from app.routes import health, ask, upload, documents

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración de entorno
ENV = os.getenv("ENV", "development")
DEBUG = ENV == "development"

# Configurar orígenes permitidos para CORS
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:4200"
).split(",")


# En producción, agregar el origen de producción
if ENV == "production":
    PROD_ORIGIN = os.getenv("FRONTEND_URL")
    if PROD_ORIGIN and PROD_ORIGIN not in ALLOWED_ORIGINS:
        ALLOWED_ORIGINS.append(PROD_ORIGIN)

logger.info(f"Starting application in {ENV} mode")
logger.info(f"Allowed CORS origins: {ALLOWED_ORIGINS}")

# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application...")
    init_db()
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    engine.dispose()
    logger.info("Application shutdown complete")

app = FastAPI(
    title="AI Knowledge Assistant",
    description="Mini RAG API para consultas sobre documentos",
    version="0.1.0",
    debug=DEBUG,
    docs_url="/api/docs" if DEBUG else None,  # Deshabilitar docs en producción por seguridad
    redoc_url="/api/redoc" if DEBUG else None,
    lifespan=lifespan,
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Manejador global de errores
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": str(exc) if DEBUG else "An unexpected error occurred"
        }
    )

# Incluir routers con prefijo /api
app.include_router(health.router, prefix="/api")
app.include_router(ask.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(documents.router, prefix="/api")

# Endpoint raíz
@app.get("/")
async def root():
    return {
        "message": "AI Knowledge Assistant API",
        "version": "0.1.0",
        "status": "running",
        "environment": ENV
    }