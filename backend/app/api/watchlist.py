import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.price import Price
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.schemas.watchlist import (
    AssetSummary,
    WatchlistItemCreate,
    WatchlistItemOut,
    WatchlistItemUpdate,
)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
logger = get_logger(__name__)


async def _get_owned_item(db: AsyncSession, item_id: uuid.UUID, user_id: uuid.UUID) -> WatchlistItem:
    result = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.id == item_id,
            WatchlistItem.user_id == user_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return item


async def _item_to_out(db: AsyncSession, item: WatchlistItem) -> WatchlistItemOut:
    asset = (await db.execute(select(Asset).where(Asset.id == item.asset_id))).scalar_one()
    price_row = (
        await db.execute(
            select(Price)
            .where(Price.asset_id == item.asset_id)
            .order_by(Price.timestamp.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    current_price = price_row.close if price_row else None
    pct = None
    if current_price is not None and item.target_price:
        pct = float((current_price - item.target_price) / item.target_price * 100)
    return WatchlistItemOut(
        id=item.id,
        asset_id=item.asset_id,
        target_price=item.target_price,
        currency=item.currency,
        notes=item.notes,
        alert_enabled=item.alert_enabled,
        alerted_at=item.alerted_at,
        created_at=item.created_at,
        asset=AssetSummary(id=asset.id, symbol=asset.symbol, name=asset.name, currency=asset.currency),
        current_price=current_price,
        pct_from_target=pct,
    )


@router.get("", response_model=list[WatchlistItemOut])
async def list_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    latest_ts = (
        select(Price.asset_id, func.max(Price.timestamp).label("max_ts"))
        .group_by(Price.asset_id)
        .subquery("latest_ts")
    )
    stmt = (
        select(WatchlistItem, Asset, Price)
        .join(Asset, WatchlistItem.asset_id == Asset.id)
        .outerjoin(latest_ts, WatchlistItem.asset_id == latest_ts.c.asset_id)
        .outerjoin(
            Price,
            and_(
                Price.asset_id == WatchlistItem.asset_id,
                Price.timestamp == latest_ts.c.max_ts,
            ),
        )
        .where(WatchlistItem.user_id == current_user.id)
        .order_by(WatchlistItem.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    out = []
    for item, asset, price in rows:
        current_price = price.close if price else None
        pct = None
        if current_price is not None and item.target_price:
            pct = float((current_price - item.target_price) / item.target_price * 100)
        out.append(
            WatchlistItemOut(
                id=item.id,
                asset_id=item.asset_id,
                target_price=item.target_price,
                currency=item.currency,
                notes=item.notes,
                alert_enabled=item.alert_enabled,
                alerted_at=item.alerted_at,
                created_at=item.created_at,
                asset=AssetSummary(id=asset.id, symbol=asset.symbol, name=asset.name, currency=asset.currency),
                current_price=current_price,
                pct_from_target=pct,
            )
        )
    return out


@router.post("", response_model=WatchlistItemOut, status_code=201)
async def add_to_watchlist(
    body: WatchlistItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == current_user.id,
                WatchlistItem.asset_id == body.asset_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Asset already in watchlist")

    asset = (await db.execute(select(Asset).where(Asset.id == body.asset_id))).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    item = WatchlistItem(
        user_id=current_user.id,
        asset_id=body.asset_id,
        target_price=body.target_price,
        currency=body.currency or asset.currency,
        notes=body.notes,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    logger.info("Watchlist item added: %s for user %s", asset.symbol, current_user.id)
    return await _item_to_out(db, item)


@router.patch("/{item_id}", response_model=WatchlistItemOut)
async def update_watchlist_item(
    item_id: uuid.UUID,
    body: WatchlistItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await _get_owned_item(db, item_id, current_user.id)
    if "target_price" in body.model_fields_set:
        item.target_price = body.target_price
    if "notes" in body.model_fields_set:
        item.notes = body.notes
    if "alert_enabled" in body.model_fields_set:
        item.alert_enabled = body.alert_enabled
    await db.commit()
    await db.refresh(item)
    return await _item_to_out(db, item)


@router.delete("/{item_id}", status_code=204)
async def delete_watchlist_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await _get_owned_item(db, item_id, current_user.id)
    await db.delete(item)
    await db.commit()


@router.post("/{item_id}/rearm", response_model=WatchlistItemOut)
async def rearm_watchlist_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await _get_owned_item(db, item_id, current_user.id)
    item.alerted_at = None
    item.alert_enabled = True
    await db.commit()
    await db.refresh(item)
    return await _item_to_out(db, item)
