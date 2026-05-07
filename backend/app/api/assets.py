import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.encryption import decrypt
from app.core.logging import get_logger
from app.models.price import Price
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate, CoinGeckoMatch
from app.schemas.price import PriceBar, PriceHistoryResponse
from app.services import asset as asset_service
from app.services.th_fund import search_th_funds

router = APIRouter(prefix="/assets", tags=["assets"])
logger = get_logger(__name__)


@router.post("", response_model=AssetResponse, status_code=201)
async def create_asset(
    body: AssetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await asset_service.create_asset(
        db, current_user.id, body.symbol, body.asset_type, body.name, body.currency, body.metadata_
    )


@router.get("", response_model=list[AssetResponse])
async def list_assets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await asset_service.get_all_assets(db, current_user.id)


@router.get("/search", response_model=list[AssetResponse])
async def search_assets(
    q: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await asset_service.search_assets(db, current_user.id, q)


@router.get("/symbol/{symbol}/history", response_model=PriceHistoryResponse)
async def get_asset_history_by_symbol(
    symbol: str,
    range: str = "1M",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return OHLCV price history for an asset looked up by symbol string."""
    days = {"1W": 7, "1M": 30, "3M": 90, "1Y": 365}
    bucket = {"1W": "1 day", "1M": "1 day", "3M": "1 week", "1Y": "1 week"}
    start = datetime.now(timezone.utc) - timedelta(days=days.get(range, 30))
    bucket_interval = bucket.get(range, "1 day")

    assets = await asset_service.search_assets(db, current_user.id, symbol)
    asset = next((a for a in assets if a.symbol.upper() == symbol.upper()), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    result = await db.execute(
        text(f"""
            SELECT
                time_bucket('{bucket_interval}'::interval, timestamp) AS timestamp,
                first(open, timestamp) AS open,
                max(high) AS high,
                min(low) AS low,
                last(close, timestamp) AS close,
                sum(volume) AS volume
            FROM prices
            WHERE asset_id = :asset_id AND timestamp >= :start
            GROUP BY 1
            ORDER BY 1
        """),
        {"asset_id": asset.id, "start": start},
    )
    rows = result.fetchall()
    bars = [
        PriceBar(
            timestamp=row.timestamp,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
        )
        for row in rows
    ]
    return PriceHistoryResponse(asset_id=asset.id, bars=bars)


@router.post("/refresh-names")
async def refresh_asset_names(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch proper names for all assets from yfinance and update the DB."""
    import asyncio
    import yfinance as yf

    assets = await asset_service.get_all_assets(db, current_user.id)

    yf_map: dict[str, uuid.UUID] = {}
    for asset in assets:
        if asset.asset_type in ("us_stock", "etf", "crypto"):
            yf_map[asset.symbol] = asset.id
        elif asset.asset_type in ("thai_stock", "thai_dr"):
            yf_map[f"{asset.symbol}.BK"] = asset.id

    if not yf_map:
        return {"updated": 0, "total": len(assets)}

    def _fetch():
        results: dict[uuid.UUID, str] = {}
        tickers = yf.Tickers(" ".join(yf_map.keys()))
        for yf_sym, asset_id in yf_map.items():
            try:
                info = tickers.tickers[yf_sym].info
                name = info.get("longName") or info.get("shortName")
                if name:
                    results[asset_id] = name
            except Exception:
                pass
        return results

    name_map = await asyncio.get_event_loop().run_in_executor(None, _fetch)

    updated = 0
    for asset in assets:
        if asset.id in name_map:
            asset.name = name_map[asset.id]
            updated += 1
    await db.commit()
    logger.info("refresh_asset_names: updated %d/%d assets for user=%s", updated, len(assets), current_user.id)
    return {"updated": updated, "total": len(assets)}


@router.get("/th-fund/lookup")
async def lookup_th_fund(
    q: str,
    current_user: User = Depends(get_current_user),
):
    """Search for active TH mutual funds by name/abbreviation via SEC API v2."""
    if not current_user.sec_api_key:
        raise HTTPException(status_code=400, detail="SEC API key not configured — add it in Settings")
    api_key = decrypt(current_user.sec_api_key)
    return await search_th_funds(q, api_key)


@router.get("/search-coingecko", response_model=list[CoinGeckoMatch])
async def search_coingecko(
    q: str = Query(..., min_length=2),
    _: User = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.coingecko.com/api/v3/search",
            params={"query": q},
        )
        resp.raise_for_status()
        data = resp.json()
    coins = data.get("coins", [])[:10]
    return [
        CoinGeckoMatch(
            id=c["id"],
            symbol=c["symbol"].upper(),
            name=c["name"],
            thumb=c.get("thumb", ""),
        )
        for c in coins
    ]


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await asset_service.get_asset(db, current_user.id, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@router.get("/{asset_id}/prices", response_model=PriceHistoryResponse)
async def get_asset_price_history(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return OHLCV price history for an asset."""
    asset = await asset_service.get_asset(db, current_user.id, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    result = await db.execute(
        select(Price)
        .where(Price.asset_id == asset_id)
        .order_by(asc(Price.timestamp))
        .limit(500)
    )
    bars = list(result.scalars().all())
    return PriceHistoryResponse(asset_id=asset_id, bars=bars)


@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await asset_service.update_asset(
        db, current_user.id, asset_id, body.model_dump(exclude_none=True)
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return updated


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await asset_service.delete_asset(db, current_user.id, asset_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
