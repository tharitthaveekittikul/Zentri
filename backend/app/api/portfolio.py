import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.asset import Asset
from app.schemas.holding import HoldingCreate, HoldingRow, HoldingUpdate, PortfolioSummary
from app.schemas.transaction import ManualTransactionCreate, TransactionCreate, TransactionResponse
from app.services import portfolio as portfolio_service
from sqlalchemy import select

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/holdings", response_model=HoldingRow, status_code=201)
async def add_holding(
    body: HoldingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holding, asset = await portfolio_service.add_holding(
        db, current_user.id, body.symbol, body.asset_type,
        body.quantity, body.avg_cost_price, body.currency,
        body.purchased_at, body.platform,
    )
    total_cost = holding.quantity * holding.avg_cost_price
    return HoldingRow(
        id=holding.id, asset_id=holding.asset_id,
        symbol=asset.symbol, asset_type=asset.asset_type,
        currency=holding.currency, platform=holding.platform,
        purchased_at=holding.purchased_at,
        outstanding_shares=holding.quantity, cost_per_share=holding.avg_cost_price,
        total_cost=total_cost,
    )


@router.get("/holdings", response_model=list[HoldingRow])
async def list_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await portfolio_service.list_holdings_with_assets(db, current_user.id)
    return [HoldingRow(**r) for r in rows]


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


@router.patch("/holdings/{holding_id}", response_model=HoldingRow)
async def update_holding(
    holding_id: uuid.UUID,
    body: HoldingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holding = await portfolio_service.get_holding(db, current_user.id, holding_id)
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")
    updated = await portfolio_service.update_holding(
        db, holding, body.model_dump(exclude_none=True)
    )
    result = await db.execute(
        select(Asset).where(Asset.id == updated.asset_id)
    )
    asset = result.scalar_one()
    total_cost = updated.quantity * updated.avg_cost_price
    return HoldingRow(
        id=updated.id, asset_id=updated.asset_id,
        symbol=asset.symbol, asset_type=asset.asset_type,
        currency=updated.currency, platform=updated.platform,
        purchased_at=updated.purchased_at,
        outstanding_shares=updated.quantity, cost_per_share=updated.avg_cost_price,
        total_cost=total_cost,
    )


@router.post("/transactions/manual", response_model=TransactionResponse, status_code=201)
async def add_manual_transaction(
    body: ManualTransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.add_manual_transaction(
        db, current_user.id, body.symbol, body.asset_type, body.type,
        body.quantity, body.price, body.fee, body.currency, body.executed_at, body.platform,
    )


@router.post("/transactions", response_model=TransactionResponse, status_code=201)
async def add_transaction(
    body: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.add_transaction(
        db, current_user.id, body.asset_id, body.type,
        body.quantity, body.price, body.fee, body.executed_at, body.platform,
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
    return await portfolio_service.get_portfolio_summary(
        db,
        current_user.id,
        current_user.currency_primary,
        current_user.currency_secondary,
    )


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
