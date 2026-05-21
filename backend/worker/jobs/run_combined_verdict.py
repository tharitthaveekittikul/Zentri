from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.combined_verdict import CombinedVerdict
from worker.jobs._base import handle_job_error

logger = get_logger(__name__)


async def job_run_combined_verdict(ctx: dict, symbol: str, user_id: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    user_uuid = uuid.UUID(user_id)
    async with SessionLocal() as db:
        try:
            from app.services.combined_verdict import run_combined_verdict
            verdict = await run_combined_verdict(symbol, user_uuid, db)
            await db.commit()
            logger.info("job_run_combined_verdict done: symbol=%s verdict_id=%s", symbol, verdict.id)
            return {"status": "done", "verdict_id": str(verdict.id)}
        except Exception as e:
            logger.exception("job_run_combined_verdict failed: symbol=%s", symbol)
            await handle_job_error(
                symbol, user_uuid, e,
                lambda asset_id: CombinedVerdict(
                    id=uuid.uuid4(),
                    user_id=user_uuid,
                    asset_id=asset_id,
                    status="error",
                    error_message=str(e),
                    verdict="hold",
                    conviction=0,
                    bull_thesis="",
                    bear_thesis="",
                    key_risks=[],
                    reasoning="",
                    based_on=[],
                    provider="",
                    model="",
                    tokens_in=0,
                    tokens_out=0,
                    cost_usd=Decimal("0"),
                ),
                db,
            )
            return {"status": "error", "error": str(e)}
