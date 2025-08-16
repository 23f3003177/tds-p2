from pydantic import BaseModel


class GeneratedCode(BaseModel):
    code: str
    libraries: list[str] = []
    is_final_answer: bool


class ErrorResponse(BaseModel):
    detail: str
