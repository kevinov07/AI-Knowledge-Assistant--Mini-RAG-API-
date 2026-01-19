from fastapi import APIRouter
from app.schemas import TextRequest

router = APIRouter()

@router.post("/process-text")
def process_text(data: TextRequest):
    word_count = len(data.text.split())
    char_count = len(data.text)
    return {"word_count": word_count, "char_count": char_count}