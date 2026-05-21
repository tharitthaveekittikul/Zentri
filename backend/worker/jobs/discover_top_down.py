from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.holding import Holding
from app.models.price import Price
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.services.llm_service import get_llm_provider
from app.services.pipeline import create_log, finish_log, create_step, finish_step

logger = get_logger(__name__)

ATH_WINDOW_DAYS = 365
DROP_MIN_PCT = 20.0
DROP_MAX_PCT = 30.0
MAX_CANDIDATES = 10

SECTOR_PROMPT = """You are a macro trend analyst. Identify 5-7 current mega-trend sectors that are structurally growing in 2025-2026 with strong institutional interest.
For each sector, list 5-8 well-known US-listed stocks (S&P 500 or NASDAQ 100 constituents) that are established market leaders in that sector.
Respond ONLY with valid JSON (no markdown, no explanation):
{"sectors": [{"name": "AI Infrastructure", "description": "GPU compute, data centers, AI software platforms", "tickers": ["NVDA", "AMD", "AVGO", "MSFT", "GOOGL", "META"]}, ...]}"""


def _parse_sectors(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        data = json.loads(text)
        if not isinstance(data.get("sectors"), list):
            return None
        return data
    except (json.JSONDecodeError, AttributeError):
        return None


async def job_discover_top_down(ctx: dict, user_id: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "top_down_discovery")
        try:
            user = (await db.execute(select(User).where(User.id == uuid.UUID(user_id)))).scalar_one_or_none()
            if not user:
                raise ValueError(f"User {user_id} not found")

            # Step 1: identify mega-trend sectors via LLM
            step_sectors = await create_step(db, log.id, "identify_sectors")
            llm_tickers: list[str] = []
            sector_names: list[str] = []
            try:
                llm = await get_llm_provider(db, "top_down_discovery")
                resp = await llm.complete([
                    {"role": "system", "content": SECTOR_PROMPT},
                    {"role": "user", "content": "List the current mega-trend sectors with their leading stocks. Respond with JSON only."},
                ])
                parsed = _parse_sectors(resp.content)
                if parsed:
                    for sector in parsed["sectors"]:
                        sector_names.append(sector["name"])
                        llm_tickers.extend(sector.get("tickers", []))
                    llm_tickers = list(dict.fromkeys(t.upper() for t in llm_tickers))
                    logger.info(
                        "discover_top_down: identified %d sectors, %d tickers from LLM",
                        len(sector_names), len(llm_tickers),
                    )
                await finish_step(db, step_sectors, success=True, metadata={
                    "sectors": sector_names,
                    "llm_tickers": len(llm_tickers),
                    "model": getattr(llm, "model", "unknown"),
                })
            except Exception as e:
                logger.warning("discover_top_down: LLM sector call failed, falling back to portfolio/watchlist: %s", e)
                await finish_step(db, step_sectors, success=True, metadata={
                    "sectors": [],
                    "llm_tickers": 0,
                    "warning": str(e)[:200],
                })

            # Collect user's portfolio + watchlist tickers to supplement LLM suggestions
            holding_assets = (await db.execute(
                select(Asset)
                .join(Holding, Holding.asset_id == Asset.id)
                .where(Holding.user_id == user.id)
            )).scalars().all()
            watchlist_assets = (await db.execute(
                select(Asset)
                .join(WatchlistItem, WatchlistItem.asset_id == Asset.id)
                .where(WatchlistItem.user_id == user.id)
            )).scalars().all()
            user_symbols = sorted({a.symbol for a in [*holding_assets, *watchlist_assets]})

            # Union: LLM-suggested first (mega-trend priority), then user holdings/watchlist
            all_symbols = list(dict.fromkeys([*llm_tickers, *user_symbols]))

            # Step 2: screen for ATH pullback
            step_screen = await create_step(db, log.id, "screen_ath")
            since = datetime.now(timezone.utc) - timedelta(days=ATH_WINDOW_DAYS)
            in_db = 0
            qualified: list[dict] = []

            for symbol in all_symbols:
                asset_result = await db.execute(select(Asset).where(Asset.symbol == symbol))
                asset = asset_result.scalar_one_or_none()
                if not asset:
                    continue
                in_db += 1

                ath_result = await db.execute(
                    select(func.max(Price.close))
                    .where(Price.asset_id == asset.id, Price.timestamp >= since)
                )
                ath = ath_result.scalar()
                if not ath:
                    continue

                latest_result = await db.execute(
                    select(Price.close)
                    .where(Price.asset_id == asset.id)
                    .order_by(Price.timestamp.desc())
                    .limit(1)
                )
                current = latest_result.scalar()
                if not current:
                    continue

                drop_pct = float(
                    (Decimal(str(ath)) - Decimal(str(current))) / Decimal(str(ath)) * 100
                )
                if DROP_MIN_PCT <= drop_pct <= DROP_MAX_PCT:
                    qualified.append({"asset": asset, "drop_pct": drop_pct})
                    logger.info("discover_top_down: %s qualifies drop=%.1f%%", asset.symbol, drop_pct)

            qualified.sort(key=lambda x: x["drop_pct"], reverse=True)
            candidates = qualified[:MAX_CANDIDATES]
            await finish_step(db, step_screen, success=True, metadata={
                "screened": len(all_symbols),
                "in_db": in_db,
                "qualified": len(qualified),
                "selected": len(candidates),
                "symbols": [c["asset"].symbol for c in candidates],
            })

            # Step 3: queue run_top_down_analysis for each candidate
            step_queue = await create_step(db, log.id, "queue_analysis")
            queued = 0
            try:
                from arq.connections import ArqRedis, RedisSettings, create_pool
                from app.core.config import settings
                redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
                for item in candidates:
                    await redis.enqueue_job(
                        "job_run_top_down_analysis",
                        item["asset"].symbol,
                        ath_drop_pct=round(item["drop_pct"], 2),
                        user_id=user_id,
                    )
                    queued += 1
                    logger.info("discover_top_down: queued analysis for %s", item["asset"].symbol)
                await redis.aclose()
            except Exception as e:
                logger.warning("discover_top_down: failed to queue jobs: %s", e)

            await finish_step(db, step_queue, success=True, metadata={
                "queued": queued,
                "symbols": [c["asset"].symbol for c in candidates],
            })
            await finish_log(db, log, success=True)
            logger.info(
                "discover_top_down done: sectors=%d candidates=%d queued=%d",
                len(sector_names), len(candidates), queued,
            )
            return {
                "sectors": sector_names,
                "screened": len(all_symbols),
                "qualified": len(qualified),
                "queued": queued,
                "symbols": [c["asset"].symbol for c in candidates],
            }

        except Exception as e:
            logger.exception("job_discover_top_down failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
