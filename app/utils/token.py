"""Helpers para generar y verificar tokens JWT de acceso a colecciones."""
import os
from datetime import datetime, timedelta
import jwt
from jwt.exceptions import InvalidTokenError


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY no está configurada en .env")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 2  # Token válido por 2 horas


def create_collection_access_token(collection_id: str) -> str:
    """
    Crea un token JWT temporal para acceso a una colección.
    
    Args:
        collection_id: ID de la colección desbloqueada
        
    Returns:
        Token JWT firmado como string
    """
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "collection_id": collection_id,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_collection_token(token: str) -> str | None:
    """
    Verifica un token de acceso a colección y devuelve el collection_id.
    
    Args:
        token: Token JWT a verificar
        
    Returns:
        collection_id si el token es válido, None si no lo es
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        collection_id: str = payload.get("collection_id")
        if collection_id is None:
            return None
        return collection_id
    except InvalidTokenError:
        return None
