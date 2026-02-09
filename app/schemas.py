from pydantic import BaseModel, Field, field_validator


class TextRequest(BaseModel):
    text: str


class ChatMessage(BaseModel):
    """
    Mensaje de chat. Se usa en el payload (history en /ask) y en la respuesta (GET /sessions/{id}).
    - En el payload: el cliente debe enviar solo role y content; id y created_at han de ser null u omitidos.
    - En la respuesta: el backend incluye id (UUID), role, content y created_at.
    """
    id: str | None = Field(default=None, description="UUID del mensaje en BD. En el payload debe ser null u omitido; solo viene en la respuesta.")
    role: str = Field(..., description="'user' o 'assistant'.")
    content: str = Field(..., description="Contenido del mensaje.")
    created_at: str | None = Field(default=None, description="Fecha del mensaje en ISO 8601. Solo en la respuesta.")

    @field_validator("id")
    @classmethod
    def id_empty_as_none(cls, v: str | None) -> str | None:
        """Si viene vacío o null, queda None; si viene string se acepta."""
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v


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
    session_id: str | None = Field(
        default=None,
        description="ID de sesión de chat. Si se envía, se carga el historial desde BD. Si no se envía, el backend crea una nueva sesión y devuelve su session_id en la respuesta para usarlo en las siguientes peticiones.",
    )
    history: list[ChatMessage] | None = Field(
        default=None,
        description="Historial opcional de la conversación. Si no se envía y sí session_id, se carga desde BD.",
    )


class FailedFile(BaseModel):
    """Entrada de la lista de archivos fallidos en la respuesta de upload."""

    filename: str = Field(..., description="Nombre del archivo que falló.")
    error: str = Field(..., description="Motivo del fallo (ej. formato no soportado, documento vacío).")


class UploadedDocument(BaseModel):
    """Documento creado e indexado correctamente."""

    id: str = Field(..., description="ID único del documento en la BD.")
    filename: str = Field(..., description="Nombre del archivo subido.")


class UploadResponse(BaseModel):
    """Respuesta del endpoint POST /api/upload."""

    files_uploaded: list[UploadedDocument] = Field(
        ...,
        description="Lista de documentos procesados e indexados correctamente (id y filename).",
    )
    failed_files: list[FailedFile] = Field(
        default_factory=list,
        description="Archivos que no se pudieron procesar, con nombre y error.",
    )
    documents_indexed: int = Field(
        ...,
        description="Número de documentos indexados (coincide con la longitud de files_uploaded).",
    )


# --- Respuestas (response_model) ---


class AskResultItem(BaseModel):
    """Un chunk recuperado por similitud en la respuesta de /ask."""
    text: str = Field(..., description="Texto del chunk.")
    document_id: str = Field(..., description="ID del documento.")
    chunk_index: int = Field(..., description="Índice del chunk en el documento.")
    score: float = Field(..., description="Distancia L2 (menor = más similar).")


class AskResponse(BaseModel):
    """Respuesta del endpoint POST /api/ask."""
    question: str = Field(..., description="Pregunta enviada.")
    answer: str = Field(..., description="Respuesta generada por el LLM.")
    results: list[AskResultItem] = Field(..., description="Chunks más similares (semillas de la búsqueda).")
    context_used: list[str] = Field(..., description="Fragmentos de texto enviados al LLM (semillas + vecinos).")
    session_id: str = Field(..., description="ID de sesión (creado por el backend si no se envió).")


class DocumentListItem(BaseModel):
    """Un documento en la lista de GET /api/documents."""
    id: str = Field(..., description="ID único del documento.")
    filename: str = Field(..., description="Nombre del archivo.")
    size: int = Field(..., description="Tamaño en bytes.")
    created_at: str | None = Field(None, description="Fecha de subida (ISO 8601).")
    chunk_count: int = Field(..., description="Número de chunks del documento.")


class DocumentTextResponse(BaseModel):
    """Respuesta de GET /api/documents/{document_id}/text."""
    document_id: str = Field(..., description="ID del documento.")
    filename: str = Field(..., description="Nombre del archivo.")
    text: str = Field(..., description="Texto completo (chunks concatenados).")


class SessionResponse(BaseModel):
    """Respuesta del endpoint GET /api/sessions/{session_id}."""
    session_id: str = Field(..., description="ID de la sesión de chat.")
    created_at: str | None = Field(None, description="Fecha de creación de la sesión (ISO 8601).")
    updated_at: str | None = Field(None, description="Fecha de última actualización (ISO 8601).")
    messages: list[ChatMessage] = Field(..., description="Mensajes en orden cronológico (id, role, content, created_at).")


class HealthResponse(BaseModel):
    """Respuesta de GET /api/health."""
    status: str = Field(..., description="'ok' si el servicio está en marcha.")