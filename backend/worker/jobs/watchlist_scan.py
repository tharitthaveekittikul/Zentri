import json
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.asset import Asset
from app.models.price import Price
from app.models.watchlist_item import WatchlistItem
from app.services.llm_gateway import LLMGateway
from app.services.pipeline import create_log, finish_log, create_step, finish_step
from app.services.price_feed import fetch_price_for_asset
from app.services.rag_service import get_or_create_collection, search

logger = get_logger(__name__)


def _parse_scan_response(text: str) -> dict | None:
    import math
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        data = json.loads(text)
        if data.get("verdict") not in ("BUY", "SELL", "HOLD", "AVOID"):
            return None
        price = data.get("suggested_price")
        if price is not None:
            if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price):
                return None
        if not isinstance(data.get("reasoning"), str):
            return None
        return data
    except (json.JSONDecodeError, AttributeError):
        return None


async def job_scan_watchlist_item(ctx: dict, item_id: str, user_id: str) -> dict:
    """ARQ job: run AI analysis on a single watchlist item."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "watchlist_scan")
        try:
            item = (await db.execute(
                select(WatchlistItem).where(WatchlistItem.id == uuid.UUID(item_id))
            )).scalar_one_or_none()
            if not item:
                raise ValueError(f"WatchlistItem {item_id} not found")

            # Step 1: load_asset
            step_load = await create_step(db, log.id, "load_asset")
            asset = (await db.execute(
                select(Asset).where(Asset.id == item.asset_id)
            )).scalar_one()

            since = datetime.now(timezone.utc) - timedelta(days=30)
            prices = (await db.execute(
                select(Price)
                .where(Price.asset_id == asset.id, Price.timestamp >= since)
                .order_by(desc(Price.timestamp))
                .limit(10)
            )).scalars().all()

            prices = await fetch_price_for_asset(db, asset) or list(prices)

            prices_txt = (
                "\n".join(f"{p.timestamp.date()}: close={p.close}" for p in prices)
                if prices else "No recent price history available."
            )
            await finish_step(db, step_load, success=True, metadata={"symbol": asset.symbol, "price_days": len(prices)})

            # Step 2: rag_retrieval
            step_rag = await create_step(db, log.id, "rag_retrieval")
            collection = get_or_create_collection(asset.symbol)
            rag_chunks = search(collection, query=f"{asset.symbol} financial analysis outlook")
            rag_context = "\n\n---\n\n".join(rag_chunks) if rag_chunks else "No research documents available."
            await finish_step(db, step_rag, success=True, metadata={"chunks_found": len(rag_chunks)})

            # Step 3: llm_call
            step_llm = await create_step(db, log.id, "llm_call")
            gateway = LLMGateway(db)
            llm_result = await gateway.complete(
                "watchlist_scan",
                uuid.UUID(user_id),
                {"symbol": asset.symbol, "prices_txt": prices_txt, "rag_context": rag_context},
            )
            parsed = _parse_scan_response(llm_result.content)
            if parsed is None:
                raise ValueError(f"LLM returned malformed JSON: {llm_result.content[:200]}")
            await finish_step(db, step_llm, success=True, metadata={
                "tokens_in": llm_result.tokens_in,
                "tokens_out": llm_result.tokens_out,
                "cost_usd": llm_result.cost_usd,
                "cost_thb": llm_result.cost_thb,
                "exchange_rate": llm_result.exchange_rate,
                "model": llm_result.model,
                "provider": llm_result.provider,
                "prompt": llm_result.prompt,
                "response": llm_result.content,
            })

            # Step 4: save_suggestion
            step_save = await create_step(db, log.id, "save_suggestion")
            suggested_price = parsed.get("suggested_price")
            analysis = AIAnalysis(
                asset_id=asset.id,
                job_id=str(log.id),
                verdict=parsed["verdict"],
                target_price=suggested_price,
                reasoning=parsed["reasoning"],
                provider="llm_gateway",
                model="watchlist_scan",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0,
            )
            db.add(analysis)
            await db.commit()
            await finish_step(db, step_save, success=True, metadata={"symbol": asset.symbol, "verdict": parsed["verdict"]})
            await finish_log(db, log, success=True)
            logger.info("watchlist_scan done item=%s verdict=%s target_price=%s", item_id, parsed["verdict"], item.target_price)
            return {"verdict": parsed["verdict"], "analysis_id": str(analysis.id)}
        except Exception as e:
            logger.exception("job_scan_watchlist_item failed item=%s: %s", item_id, e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_scan_watchlist_batch(ctx: dict) -> dict:
    """ARQ job: enqueue scan jobs for every watchlist item."""
    from arq.connections import ArqRedis

    SessionLocal: async_sessionmaker = ctx["session_factory"]
    redis: ArqRedis = ctx["redis"]

    async with SessionLocal() as db:
        items = (await db.execute(select(WatchlistItem))).scalars().all()

    count = 0
    for item in items:
        await redis.enqueue_job("job_scan_watchlist_item", str(item.id), str(item.user_id))
        count += 1

    logger.info("watchlist batch scan: queued %d items", count)
    return {"queued": count}
