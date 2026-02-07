from pydantic import BaseModel, Field


class TextRequest(BaseModel):
    text: str


class QuestionRequest(BaseModel):
    """Cuerpo de la petición para el endpoint /api/ask."""
    question: str = Field(
        ...,
        description="Pregunta a responder usando los documentos indexados.",
        examples=["¿Cuáles son los principios del diseño ágil?"],
    )
    k: int = Field(
        5,
        ge=1,
        le=20,
        description="Número de chunks a recuperar por similitud (default: 5). A mayor k, más contexto pero más tokens.",
    )


class FailedFile(BaseModel):
    """Entrada de la lista de archivos fallidos en la respuesta de upload."""

    filename: str = Field(..., description="Nombre del archivo que falló.")
    error: str = Field(..., description="Motivo del fallo (ej. formato no soportado, documento vacío).")


class UploadResponse(BaseModel):
    """Respuesta del endpoint POST /api/upload."""

    files_uploaded: list[str] = Field(
        ...,
        description="Lista de nombres de archivos procesados e indexados correctamente.",
    )
    failed_files: list[FailedFile] = Field(
        default_factory=list,
        description="Archivos que no se pudieron procesar, con nombre y error.",
    )
    documents_indexed: int = Field(
        ...,
        description="Número de documentos indexados (coincide con la longitud de files_uploaded).",
    )
