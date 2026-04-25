from pydantic import BaseModel


class ImportPreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict]


class ImportRow(BaseModel):
    date: str
    symbol: str
    type: str
    quantity: str
    price: str
    fee: str = "0"


class ImportConfirmRequest(BaseModel):
    rows: list[ImportRow]
    asset_type: str = "us_stock"
    save_profile: bool = False
    broker_name: str | None = None


class ImportConfirmResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = []
