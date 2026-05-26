import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from arq.connections import RedisSettings, create_pool

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.constants import ATH_WINDOW_DAYS
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.asset import Asset
from app.models.feature_llm_config import FeatureLLMConfig
from app.models.price import Price
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.models.watchlist_suggestion import WatchlistSuggestion
from app.services.price_feed import fetch_price_for_asset
from app.schemas.common import PaginatedResponse
from app.schemas.watchlist import (
    AssetSummary,
    WatchlistItemCreate,
    WatchlistItemOut,
    WatchlistItemUpdate,
    WatchlistSuggestionOut,
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


async def _get_owned_suggestion(
    db: AsyncSession, suggestion_id: uuid.UUID, user_id: uuid.UUID
) -> WatchlistSuggestion:
    result = await db.execute(
        select(WatchlistSuggestion).where(
            WatchlistSuggestion.id == suggestion_id,
            WatchlistSuggestion.user_id == user_id,
        )
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return suggestion


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

    since_ath = datetime.now(timezone.utc) - timedelta(days=ATH_WINDOW_DAYS)
    ath_result = await db.execute(
        select(func.max(Price.close))
        .where(Price.asset_id == item.asset_id, Price.timestamp >= since_ath)
    )
    ath = ath_result.scalar()
    ath_drop_pct = None
    if ath and current_price:
        ath_drop_pct = float(
            (Decimal(str(ath)) - Decimal(str(current_price))) / Decimal(str(ath)) * 100
        )

    analysis = (
        await db.execute(
            select(AIAnalysis)
            .where(AIAnalysis.asset_id == item.asset_id)
            .order_by(AIAnalysis.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return WatchlistItemOut(
        id=item.id,
        asset_id=item.asset_id,
        target_price=item.target_price,
        currency=item.currency,
        notes=item.notes,
        alert_enabled=item.alert_enabled,
        alerted_at=item.alerted_at,
        created_at=item.created_at,
        asset=AssetSummary(id=asset.id, symbol=asset.symbol, name=asset.name, currency=asset.currency, asset_type=asset.asset_type, metadata_=asset.metadata_ or {}),
        current_price=current_price,
        pct_from_target=pct,
        last_verdict=analysis.verdict if analysis else None,
        ai_suggested_price=analysis.target_price if analysis else None,
        last_scanned_at=analysis.created_at if analysis else None,
        ath_alert_threshold=item.ath_alert_threshold,
        ath_alerted_at=item.ath_alerted_at,
        ath_drop_pct=ath_drop_pct,
    )


@router.get("", response_model=PaginatedResponse[WatchlistItemOut])
async def list_watchlist(
    search: str | None = None,
    asset_type: str | None = None,
    alert_status: str | None = None,
    page: int = 1,
    page_size: int = 25,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_q_count = (
        select(func.count(WatchlistItem.id))
        .select_from(WatchlistItem)
        .join(Asset, Asset.id == WatchlistItem.asset_id)
        .where(WatchlistItem.user_id == current_user.id)
    )
    base_q_data = (
        select(WatchlistItem)
        .join(Asset, Asset.id == WatchlistItem.asset_id)
        .where(WatchlistItem.user_id == current_user.id)
    )

    if search:
        flt = or_(Asset.symbol.ilike(f"%{search}%"), Asset.name.ilike(f"%{search}%"))
        base_q_count = base_q_count.where(flt)
        base_q_data = base_q_data.where(flt)
    if asset_type:
        base_q_count = base_q_count.where(Asset.asset_type == asset_type)
        base_q_data = base_q_data.where(Asset.asset_type == asset_type)
    if alert_status == "enabled":
        flt = and_(WatchlistItem.alert_enabled.is_(True), WatchlistItem.alerted_at.is_(None))
        base_q_count = base_q_count.where(flt)
        base_q_data = base_q_data.where(flt)
    elif alert_status == "triggered":
        flt = WatchlistItem.alerted_at.isnot(None)
        base_q_count = base_q_count.where(flt)
        base_q_data = base_q_data.where(flt)
    elif alert_status == "disabled":
        flt = WatchlistItem.alert_enabled.is_(False)
        base_q_count = base_q_count.where(flt)
        base_q_data = base_q_data.where(flt)

    total: int = (await db.execute(base_q_count)).scalar_one()

    if total == 0:
        return PaginatedResponse(items=[], total=0, page=1, page_size=page_size)

    max_page = (total + page_size - 1) // page_size
    page = max(1, min(page, max_page))
    offset = (page - 1) * page_size

    result = await db.execute(
        base_q_data.order_by(WatchlistItem.created_at.desc()).offset(offset).limit(page_size)
    )
    db_items = list(result.scalars().all())
    out_items = [await _item_to_out(db, item) for item in db_items]
    return PaginatedResponse(items=out_items, total=total, page=page, page_size=page_size)


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
    if "ath_alert_threshold" in body.model_fields_set:
        item.ath_alert_threshold = body.ath_alert_threshold
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
    item.ath_alerted_at = None
    item.alert_enabled = True
    await db.commit()
    await db.refresh(item)
    return await _item_to_out(db, item)


@router.post("/{item_id}/scan")
async def trigger_item_scan(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await _get_owned_item(db, item_id, current_user.id)
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_scan_watchlist_item", str(item.id), str(current_user.id))
        await redis.aclose()
        logger.info("watchlist scan enqueued item=%s job=%s", item_id, job.job_id if job else None)
    except Exception:
        logger.exception("Failed to enqueue scan for item %s", item_id)
    return {"queued": True, "item_id": str(item_id)}


@router.post("/{item_id}/fetch-prices")
async def fetch_item_prices(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await _get_owned_item(db, item_id, current_user.id)
    asset = (await db.execute(select(Asset).where(Asset.id == item.asset_id))).scalar_one()
    rows = await fetch_price_for_asset(db, asset)
    logger.info("fetch-prices: %d rows for item=%s symbol=%s", len(rows), item_id, asset.symbol)
    return {"fetched": len(rows), "symbol": asset.symbol}


@router.post("/scan-all")
async def trigger_scan_all(current_user: User = Depends(get_current_user)):
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_scan_watchlist_batch")
        await redis.aclose()
        logger.info("watchlist batch scan enqueued job=%s", job.job_id if job else None)
    except Exception:
        logger.exception("Failed to enqueue batch scan")
    return {"queued": True}


@router.post("/discover")
async def trigger_discover(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    config = (await db.execute(
        select(FeatureLLMConfig).where(
            FeatureLLMConfig.feature_key == "watchlist_discovery",
            FeatureLLMConfig.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=422,
            detail="no_llm_config",
        )
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_discover_watchlist", str(current_user.id))
        await redis.aclose()
        logger.info("watchlist discovery enqueued job=%s", job.job_id if job else None)
    except Exception:
        logger.exception("Failed to enqueue discovery")
    return {"queued": True}


@router.get("/suggestions", response_model=list[WatchlistSuggestionOut])
async def list_suggestions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WatchlistSuggestion)
        .where(
            WatchlistSuggestion.user_id == current_user.id,
            WatchlistSuggestion.status == "pending",
        )
        .order_by(WatchlistSuggestion.created_at.desc())
    )
    return result.scalars().all()


@router.post("/suggestions/{suggestion_id}/accept", response_model=WatchlistItemOut, status_code=201)
async def accept_suggestion(
    suggestion_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    suggestion = await _get_owned_suggestion(db, suggestion_id, current_user.id)

    asset_id = suggestion.asset_id
    if asset_id is None:
        sym = suggestion.symbol.upper()
        asset_row = (await db.execute(
            select(Asset).where(Asset.user_id == current_user.id, Asset.symbol == sym)
        )).scalar_one_or_none()
        if asset_row is None:
            asset_row = Asset(
                user_id=current_user.id,
                symbol=sym,
                name=sym,
                asset_type="us_stock",
                currency="USD",
            )
            db.add(asset_row)
            await db.flush()
            logger.info("Created stub asset for watchlist: %s user=%s", sym, current_user.id)
        asset_id = asset_row.id

    existing = (await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == current_user.id,
            WatchlistItem.asset_id == asset_id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Asset already in watchlist")

    item = WatchlistItem(
        user_id=current_user.id,
        asset_id=asset_id,
        target_price=suggestion.suggested_price,
        alert_enabled=suggestion.suggested_price is not None,
    )
    db.add(item)
    suggestion.status = "accepted"
    await db.commit()
    await db.refresh(item)
    logger.info("Suggestion accepted: %s → WatchlistItem", suggestion.symbol)
    return await _item_to_out(db, item)


@router.post("/suggestions/{suggestion_id}/dismiss", status_code=204)
async def dismiss_suggestion(
    suggestion_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    suggestion = await _get_owned_suggestion(db, suggestion_id, current_user.id)
    suggestion.status = "dismissed"
    await db.commit()
