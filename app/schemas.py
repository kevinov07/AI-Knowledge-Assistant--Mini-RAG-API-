from pydantic import BaseModel

class TextRequest(BaseModel):
    text: str

class QuestionRequest(BaseModel):
    question: str
    k: int = 3