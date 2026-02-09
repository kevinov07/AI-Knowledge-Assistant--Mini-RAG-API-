"""
Endpoints para sesiones de chat: obtener mensajes de una conversación.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Session as SessionModel, ChatMessage as ChatMessageModel
from app.schemas import SessionResponse, ChatMessage

router = APIRouter()


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="Obtener una sesión (metadata + mensajes)",
    response_description="Sesión con id, fechas y lista de mensajes en orden cronológico.",
)
def get_session(session_id: str, db: Session = Depends(get_db)):
    """
    Devuelve la sesión con su metadata (created_at, updated_at) y todos sus mensajes.

    Un solo request para restaurar la conversación en el frontend: al cargar con un
    session_id guardado (p. ej. en localStorage), el cliente hace GET y muestra
    la conversación completa.
    """
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    rows = (
        db.execute(
            select(ChatMessageModel.id, ChatMessageModel.role, ChatMessageModel.content, ChatMessageModel.created_at)
            .where(ChatMessageModel.session_id == session_id)
            .order_by(ChatMessageModel.created_at.asc())
        )
        .fetchall()
    )

    return SessionResponse(
        session_id=session_id,
        created_at=session.created_at.isoformat() if session.created_at else None,
        updated_at=session.updated_at.isoformat() if session.updated_at else None,
        messages=[
            ChatMessage(
                id=r.id,
                role=r.role,
                content=r.content,
                created_at=r.created_at.isoformat() if r.created_at else None,
            )
            for r in rows
        ],
    )
