import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.holding import Holding
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.models.watchlist_suggestion import WatchlistSuggestion
from app.services.llm_gateway import LLMGateway
from app.services.pipeline import create_log, finish_log, create_step, finish_step

logger = get_logger(__name__)


def _parse_discovery_response(text: str) -> list[dict] | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        data = json.loads(text)
        if not isinstance(data, list):
            return None
        valid = [
            item for item in data
            if item.get("verdict") in ("BUY", "SELL", "HOLD")
            and item.get("symbol")
            and item.get("reasoning")
        ]
        return valid or None
    except (json.JSONDecodeError, AttributeError):
        return None


async def job_discover_watchlist(ctx: dict, user_id: str) -> dict:
    """ARQ job: ask LLM to suggest new tickers based on portfolio, save as WatchlistSuggestion rows."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "watchlist_discovery")
        try:
            user = (await db.execute(select(User).where(User.id == uuid.UUID(user_id)))).scalar_one_or_none()
            if not user:
                raise ValueError(f"User {user_id} not found")

            # Step 1: load_portfolio
            step_load = await create_step(db, log.id, "load_portfolio")
            holdings_rows = (await db.execute(
                select(Holding, Asset)
                .join(Asset, Holding.asset_id == Asset.id)
                .where(Holding.user_id == user.id)
            )).all()
            holdings_txt = (
                "\n".join(f"- {asset.symbol} ({asset.name}): {h.quantity} units" for h, asset in holdings_rows)
                if holdings_rows else "No holdings yet."
            )
            portfolio_symbols = {asset.symbol for _, asset in holdings_rows}

            watchlist_rows = (await db.execute(
                select(WatchlistItem, Asset)
                .join(Asset, WatchlistItem.asset_id == Asset.id)
                .where(WatchlistItem.user_id == user.id)
            )).all()
            watchlist_symbols = {asset.symbol for _, asset in watchlist_rows}
            watchlist_txt = ", ".join(watchlist_symbols) if watchlist_symbols else "None"

            pending_symbols = set(
                (await db.execute(
                    select(WatchlistSuggestion.symbol).where(
                        WatchlistSuggestion.user_id == user.id,
                        WatchlistSuggestion.status == "pending",
                    )
                )).scalars().all()
            )
            await finish_step(db, step_load, success=True, metadata={
                "holdings": len(holdings_rows),
                "watchlist": len(watchlist_rows),
            })

            # Step 2: llm_call
            step_llm = await create_step(db, log.id, "llm_call")
            gateway = LLMGateway(db)
            llm_result = await gateway.complete(
                "watchlist_discovery",
                user.id,
                {"holdings_txt": holdings_txt, "watchlist_txt": watchlist_txt},
            )
            logger.info("LLM watchlist_discovery response received, length=%d", len(llm_result.content))
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

            parsed = _parse_discovery_response(llm_result.content)
            if parsed is None:
                raise ValueError(f"LLM returned malformed JSON: {llm_result.content[:200]}")

            # Step 3: save_suggestions
            step_save = await create_step(db, log.id, "save_suggestions")
            saved = 0
            skipped = 0
            for item in parsed:
                sym = item["symbol"].upper()
                if sym in portfolio_symbols or sym in watchlist_symbols or sym in pending_symbols:
                    logger.debug("Skipping duplicate symbol: %s", sym)
                    skipped += 1
                    continue

                asset_row = (await db.execute(
                    select(Asset).where(Asset.symbol == sym)
                )).scalar_one_or_none()

                db.add(WatchlistSuggestion(
                    user_id=user.id,
                    symbol=sym,
                    asset_id=asset_row.id if asset_row else None,
                    reasoning=item["reasoning"],
                    suggested_price=item.get("suggested_price"),
                    verdict=item["verdict"],
                    status="pending",
                ))
                saved += 1
                logger.debug("Queued suggestion: symbol=%s verdict=%s", sym, item["verdict"])

            await db.commit()
            await finish_step(db, step_save, success=True, metadata={"saved": saved, "skipped": skipped})
            await finish_log(db, log, success=True)
            logger.info("watchlist_discover done: %d suggestions saved", saved)
            return {"suggestions_saved": saved}
        except Exception as e:
            logger.exception("job_discover_watchlist failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
