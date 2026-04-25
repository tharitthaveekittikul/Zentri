import csv
import io
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.csv_import import ImportConfirmRequest, ImportConfirmResponse, ImportPreviewResponse
from app.schemas.holding import HoldingCreate, HoldingResponse, PortfolioSummary
from app.schemas.transaction import TransactionCreate, TransactionResponse
from app.services import csv_import as csv_import_service
from app.services import portfolio as portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/holdings", response_model=HoldingResponse, status_code=201)
async def add_holding(
    body: HoldingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.add_holding(
        db, current_user.id, body.asset_id, body.quantity, body.avg_cost_price, body.currency
    )


@router.get("/holdings", response_model=list[HoldingResponse])
async def list_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.list_holdings(db, current_user.id)


@router.delete("/holdings/{holding_id}", status_code=204)
async def delete_holding(
    holding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holding = await portfolio_service.get_holding(db, current_user.id, holding_id)
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")
    await portfolio_service.delete_holding(db, holding)
    return Response(status_code=204)


@router.post("/transactions", response_model=TransactionResponse, status_code=201)
async def add_transaction(
    body: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.add_transaction(
        db, current_user.id, body.asset_id, body.type, body.quantity,
        body.price, body.fee, body.executed_at, body.platform_id
    )


@router.get("/transactions", response_model=list[TransactionResponse])
async def list_transactions(
    asset_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.list_transactions(db, current_user.id, asset_id)


@router.get("/summary", response_model=PortfolioSummary)
async def portfolio_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.get_portfolio_summary(db, current_user.id)


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def import_preview(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 10MB.",
        )
    return csv_import_service.parse_csv_preview(content)


@router.post("/import/confirm", response_model=ImportConfirmResponse)
async def import_confirm(
    body: ImportConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = [r.model_dump() for r in body.rows]
    result = await csv_import_service.confirm_import(
        db, current_user.id, rows, body.asset_type, body.save_profile, body.broker_name
    )
    return ImportConfirmResponse(**result)


@router.get("/export")
async def export_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    transactions = await portfolio_service.list_transactions(db, current_user.id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "asset_id", "type", "quantity", "price", "fee", "source", "executed_at"])
    for tx in transactions:
        writer.writerow([
            str(tx.id), str(tx.asset_id), tx.type,
            str(tx.quantity), str(tx.price), str(tx.fee),
            tx.source, tx.executed_at.isoformat()
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=zentri-portfolio.csv"},
    )
