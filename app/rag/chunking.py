"""
Chunking con LangChain RecursiveCharacterTextSplitter.
Corta respetando párrafos (\\n\\n), luego líneas (\\n), luego espacios.
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Tamaño y solapamiento en caracteres (~equivalente a ~100 palabras / 20 overlap).
DEFAULT_CHUNK_SIZE = 600
DEFAULT_CHUNK_OVERLAP = 100


def _get_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
        strip_whitespace=True,
    )


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """
    Divide el texto en chunks respetando párrafos y frases cuando sea posible.
    chunk_size y chunk_overlap están en caracteres.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    if not text or not text.strip():
        return []
    splitter = _get_splitter(chunk_size, chunk_overlap)
    chunks = splitter.split_text(text.strip())
    return [c for c in chunks if c.strip()]
