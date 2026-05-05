from pydantic import BaseModel


class UploadResponse(BaseModel):
    rows: list[dict]
    method: str  # "direct" | "llm_translated"
    total: int


class ConfirmRequest(BaseModel):
    rows: list[dict]


class ConfirmResponse(BaseModel):
    imported: int
    errors: list[dict]
