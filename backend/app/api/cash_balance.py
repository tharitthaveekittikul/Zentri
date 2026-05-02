import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.cash_balance import CashBalanceCreate, CashBalanceOut
from app.services import cash_balance as cash_service

router = APIRouter(prefix="/cash-balances", tags=["cash-balances"])


@router.post("", response_model=CashBalanceOut, status_code=status.HTTP_201_CREATED)
async def create_balance(
    body: CashBalanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await cash_service.create_snapshot(
        db, current_user.id, body.asset_id, body.balance, body.snapshot_date, body.notes
    )


@router.get("/{asset_id}/latest", response_model=CashBalanceOut)
async def get_latest_balance(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snap = await cash_service.get_latest(db, current_user.id, asset_id)
    if not snap:
        raise HTTPException(status_code=404, detail="No balance snapshot found")
    return snap


@router.get("/{asset_id}/history", response_model=list[CashBalanceOut])
async def get_balance_history(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await cash_service.get_history(db, current_user.id, asset_id)
