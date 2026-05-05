import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arq.connections import RedisSettings, create_pool

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.asset import Asset
from app.models.feature_llm_config import FeatureLLMConfig
from app.models.price import Price
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.models.watchlist_suggestion import WatchlistSuggestion
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
        asset=AssetSummary(id=asset.id, symbol=asset.symbol, name=asset.name, currency=asset.currency),
        current_price=current_price,
        pct_from_target=pct,
        last_verdict=analysis.verdict if analysis else None,
        ai_suggested_price=analysis.target_price if analysis else None,
        last_scanned_at=analysis.created_at if analysis else None,
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

    asset_ids = [row[1].id for row in rows]
    analyses: dict[uuid.UUID, AIAnalysis] = {}
    if asset_ids:
        latest_a_ts = (
            select(AIAnalysis.asset_id, func.max(AIAnalysis.created_at).label("max_ts"))
            .where(AIAnalysis.asset_id.in_(asset_ids))
            .group_by(AIAnalysis.asset_id)
            .subquery("latest_a_ts")
        )
        for a in (
            await db.execute(
                select(AIAnalysis).join(
                    latest_a_ts,
                    and_(
                        AIAnalysis.asset_id == latest_a_ts.c.asset_id,
                        AIAnalysis.created_at == latest_a_ts.c.max_ts,
                    ),
                )
            )
        ).scalars().all():
            analyses[a.asset_id] = a

    out = []
    for item, asset, price in rows:
        current_price = price.close if price else None
        pct = None
        if current_price is not None and item.target_price:
            pct = float((current_price - item.target_price) / item.target_price * 100)
        analysis = analyses.get(asset.id)
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
                last_verdict=analysis.verdict if analysis else None,
                ai_suggested_price=analysis.target_price if analysis else None,
                last_scanned_at=analysis.created_at if analysis else None,
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
