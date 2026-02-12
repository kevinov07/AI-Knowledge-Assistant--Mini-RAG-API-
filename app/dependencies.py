"""Dependencies para validación de tokens y permisos."""
from fastapi import Header, HTTPException, Depends, Path
from sqlalchemy.orm import Session

from app.utils.token import verify_collection_token
from app.db.database import get_db
from app.db.models import Collection as CollectionModel


def get_collection_with_access(
    collection_id: str = Path(..., description="ID de la colección"),
    authorization: str | None = Header(default=None, description="Bearer token de acceso (requerido solo para colecciones privadas)"),
    db: Session = Depends(get_db),
) -> CollectionModel:
    """
    Dependency que valida acceso a una colección (pública o privada con token).
    
    Lógica:
    - Colección pública sin token: ✅ permitido
    - Colección pública con token válido: ✅ permitido
    - Colección privada sin token: ❌ 401
    - Colección privada con token válido: ✅ permitido
    - Colección privada con token inválido: ❌ 401
    - Token de otra colección: ❌ 403
    
    Uso:
        collection = Depends(get_collection_with_access)
    """

    # Buscar la colección
    collection = db.get(CollectionModel, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Colección no encontrada.")
    
    # Si es pública, permitir acceso con o sin token
    if collection.is_public:
        # Si envían token, validar que sea correcto (opcional pero si lo envían debe ser válido)
        if authorization and authorization.strip():
            if not authorization.startswith("Bearer "):
                print("TOKEN DE AUTORIZACIÓN INVÁLIDO. USE 'BEARER <TOKEN>'")
                raise HTTPException(
                    status_code=401,
                    detail="Token de autorización inválido. Use 'Bearer <token>'",
                )
            token = authorization.replace("Bearer ", "").strip()
            token_collection_id = verify_collection_token(token)
            if token_collection_id and token_collection_id != collection_id:
                print("el token no corresponde a esta coleccion.")
                raise HTTPException(
                    status_code=403,
                    detail="El token no corresponde a esta colección.",
                )
        return collection
    
    # Si es privada, requerir token válido
    if not authorization or not authorization.strip():
        raise HTTPException(
            status_code=401,
            detail="Esta colección es privada. Debe desbloquearla primero con POST /collections/{id}/unlock",
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Token de autorización inválido. Use 'Bearer <token>'",
        )
    
    token = authorization.replace("Bearer ", "").strip()
    token_collection_id = verify_collection_token(token)
    
    if not token_collection_id:
        raise HTTPException(
            status_code=401,
            detail="Token inválido o expirado. Desbloquee la colección nuevamente.",
        )
    
    if token_collection_id != collection_id:
        raise HTTPException(
            status_code=403,
            detail="El token no corresponde a esta colección.",
        )
    
    return collection


def get_collection_from_token(
    authorization: str = Header(..., description="Bearer token de acceso a la colección"),
    db: Session = Depends(get_db),
) -> CollectionModel:
    """
    Dependency que SIEMPRE requiere token válido (usado para endpoints donde el token es obligatorio).
    
    Uso:
        collection = Depends(get_collection_from_token)
        
    Lanza HTTPException 401 si:
    - No se envía token
    - El token es inválido o expirado
    - La colección no existe
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Token de autorización inválido. Use 'Bearer <token>'",
        )
    
    token = authorization.replace("Bearer ", "")
    collection_id = verify_collection_token(token)
    
    if not collection_id:
        raise HTTPException(
            status_code=401,
            detail="Token inválido o expirado. Desbloquee la colección nuevamente.",
        )
    
    collection = db.get(CollectionModel, collection_id)
    if not collection:
        raise HTTPException(
            status_code=404,
            detail="La colección asociada al token no existe.",
        )
    
    return collection


def get_optional_collection_from_token(
    authorization: str | None = Header(default=None, description="Bearer token opcional"),
    db: Session = Depends(get_db),
) -> CollectionModel | None:
    """
    Dependency opcional: valida token si se envía, devuelve None si no.
    
    Útil para endpoints que funcionan sin colección pero aceptan token para filtrar por colección.
    """
    if not authorization or not authorization.strip():
        return None
    
    if not authorization.startswith("Bearer "):
        return None
    
    token = authorization.replace("Bearer ", "").strip()
    collection_id = verify_collection_token(token)
    
    if not collection_id:
        return None
    
    return db.get(CollectionModel, collection_id)
