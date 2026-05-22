from __future__ import annotations

import asyncio
import uuid

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset

logger = get_logger(__name__)

_STATIC_SECTOR: dict[str, str] = {
    "crypto": "Crypto",
    "gold": "Commodities",
    "cash": "Cash",
    "th_fund": "Mutual Fund",
}

_MC_THRESHOLDS = [
    (10_000_000_000, "Large Cap"),
    (2_000_000_000, "Mid Cap"),
]


def _categorize_market_cap(market_cap: int | None) -> str | None:
    if not market_cap:
        return None
    for threshold, label in _MC_THRESHOLDS:
        if market_cap >= threshold:
            return label
    return "Small Cap"


async def enrich_assets(db: AsyncSession, user_id: uuid.UUID) -> dict:
    result = await db.execute(select(Asset).where(Asset.user_id == user_id))
    assets = list(result.scalars().all())

    enriched = 0
    for asset in assets:
        static = _STATIC_SECTOR.get(asset.asset_type)
        if static:
            asset.sector = static
            asset.industry = static
            enriched += 1

    yf_map: dict[str, uuid.UUID] = {}
    for asset in assets:
        if asset.asset_type in ("us_stock", "etf"):
            yf_map[asset.symbol] = asset.id
        elif asset.asset_type in ("thai_stock", "thai_dr"):
            yf_map[f"{asset.symbol}.BK"] = asset.id
    if yf_map:
        def _fetch() -> dict[uuid.UUID, dict]:
            out: dict[uuid.UUID, dict] = {}
            tickers = yf.Tickers(" ".join(yf_map.keys()))
            for yf_sym, asset_id in yf_map.items():
                try:
                    info = tickers.tickers[yf_sym].info
                    out[asset_id] = {
                        "sector": info.get("sector") or info.get("category"),
                        "industry": info.get("industry") or info.get("fundFamily"),
                        "market_cap": info.get("marketCap"),
                    }
                except Exception as e:
                    logger.warning("enrich_assets: yfinance failed for %s: %s", yf_sym, e)
            return out

        info_map = await asyncio.get_running_loop().run_in_executor(None, _fetch)

        asset_by_id = {a.id: a for a in assets}
        for asset_id, info in info_map.items():
            asset = asset_by_id.get(asset_id)
            if not asset:
                continue
            if info.get("sector"):
                asset.sector = info["sector"]
            if info.get("industry"):
                asset.industry = info["industry"]
            asset.market_cap_category = _categorize_market_cap(info.get("market_cap"))
            enriched += 1

    await db.commit()
    logger.info("enrich_assets: enriched %d/%d assets for user=%s", enriched, len(assets), user_id)
    return {"enriched": enriched, "total": len(assets)}
