from pydantic import BaseModel

class TextRequest(BaseModel):
    text: str

class QuestionRequest(BaseModel):
    question: str
    k: int = 3


class FailedFile(BaseModel):
    filename: str
    error: str

class UploadResponse(BaseModel):
    files_uploaded: list[str]
    failed_files: list[FailedFile]
    documents_indexed: int
