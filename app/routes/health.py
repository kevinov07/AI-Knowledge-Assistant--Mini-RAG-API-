"""
Endpoint de comprobación de estado para orquestadores, load balancers y monitorización.
"""
from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Comprobar que la API está en marcha",
    response_description="Objeto con status ok si el servicio responde.",
)
def health_check():
    """
    Responde con 200 y `{"status": "ok"}` si el proceso está vivo.
    Útil para liveness/readiness probes (Kubernetes, Docker, Render, etc.) y monitorización.
    """
    return HealthResponse(status="ok")