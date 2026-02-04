def get_context_chunks(
    chunks_metadata: dict,
    document_id: str,
    center_index: int,
    window: int = 1
) -> list[str]:
    """
    Recupera chunks vecinos de un documento para expandir el contexto alrededor de un chunk central.
    
    Útil para no cortar ideas a mitad: si recuperas el chunk 3 por similitud, también obtienes
    los chunks 1, 2, 4, 5 (con window=2) para tener contexto completo.
    
    Args:
        chunks_metadata: Diccionario con metadata de todos los chunks (chunk_id -> {document_id, chunk_index, text, ...}).
        document_id: ID del documento del cual recuperar chunks.
        center_index: Índice del chunk central (el recuperado por similitud).
        window: Radio de expansión. Con window=2, recupera chunks desde (center_index - 2) hasta (center_index + 2).
    
    Returns:
        Lista de textos de chunks ordenados por chunk_index (del mismo documento, dentro del rango).
    """
    relevant = []

    for chunk_id, data in chunks_metadata.items():
        if data["document_id"] != document_id:
            continue

        if abs(data["chunk_index"] - center_index) <= window:
            relevant.append(data)

    relevant.sort(key=lambda c: c["chunk_index"])

    return [c["text"] for c in relevant]
