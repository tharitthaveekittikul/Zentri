import uuid
from datetime import datetime, time, timezone
from decimal import Decimal

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.asset import Asset
from app.models.holding import Holding
from app.models.user import User
from app.schemas.dividend import (
    DividendCalendarResponse,
    DividendConfirmRequest,
    DividendEventOut,
)
from app.schemas.transaction import TransactionResponse
from app.services import dividend_feed, portfolio as portfolio_service

router = APIRouter(prefix="/dividends", tags=["dividends"])


@router.get("/calendar", response_model=DividendCalendarResponse)
async def get_calendar(
    months: int = 3,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if months < 1 or months > 12:
        raise HTTPException(status_code=400, detail="months must be between 1 and 12")
    result = await dividend_feed.get_calendar(
        db, current_user.id, months, current_user.currency_secondary
    )
    return result


@router.get("/upcoming", response_model=list[DividendEventOut])
async def get_upcoming(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await dividend_feed.get_upcoming(db, current_user.id, current_user.currency_secondary)


@router.post("/refresh", status_code=202)
async def refresh_dividends():
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    await redis.enqueue_job("job_fetch_dividends")
    await redis.aclose()
    return {"status": "queued"}


@router.post("/{event_id}/confirm", response_model=TransactionResponse)
async def confirm_dividend(
    event_id: uuid.UUID,
    body: DividendConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await dividend_feed.get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Dividend event not found")
    if event.status == "paid":
        raise HTTPException(status_code=400, detail="Dividend already confirmed")

    result = await db.execute(select(Asset).where(Asset.id == event.asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    holding_result = await db.execute(
        select(Holding).where(Holding.asset_id == event.asset_id, Holding.user_id == current_user.id)
    )
    if holding_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="You do not hold this asset")

    executed_dt = datetime.combine(body.executed_at, time.min).replace(tzinfo=timezone.utc)
    tx = await portfolio_service.add_transaction(
        db,
        current_user.id,
        event.asset_id,
        "dividend",
        body.quantity,
        event.amount_per_share,
        Decimal("0"),
        executed_dt,
        platform=None,
        source="manual",
    )

    event.confirmed_transaction_id = tx.id
    event.status = "paid"
    event.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return tx
