def get_context_chunks(
    chunks_metadata: dict,
    document_id: str,
    center_index: int,
    window: int = 1
):
    relevant = []

    for chunk_id, data in chunks_metadata.items():
        if data["document_id"] != document_id:
            continue

        if abs(data["chunk_index"] - center_index) <= window:
            relevant.append(data)

    relevant.sort(key=lambda c: c["chunk_index"])

    return [c["text"] for c in relevant]
