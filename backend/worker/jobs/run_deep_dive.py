from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.deep_dive_analysis import DeepDiveAnalysis
from worker.jobs._base import handle_job_error

logger = get_logger(__name__)


async def job_run_deep_dive(ctx: dict, symbol: str, user_id: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    user_uuid = uuid.UUID(user_id)
    async with SessionLocal() as db:
        try:
            from app.services.deep_dive_analysis import run_deep_dive
            analysis = await run_deep_dive(symbol, user_uuid, db)
            await db.commit()
            logger.info("job_run_deep_dive done: symbol=%s analysis_id=%s", symbol, analysis.id)
            return {"status": "done", "analysis_id": str(analysis.id)}
        except Exception as e:
            logger.exception("job_run_deep_dive failed: symbol=%s", symbol)
            await handle_job_error(
                symbol, user_uuid, e,
                lambda asset_id: DeepDiveAnalysis(
                    id=uuid.uuid4(),
                    user_id=user_uuid,
                    asset_id=asset_id,
                    status="error",
                    error_message=str(e),
                    business_model="",
                    moat_edge_type="none",
                    moat_summary="",
                    moat_competitors=[],
                    catalysts=[],
                    asymmetry_verdict="no",
                    asymmetry_floor="",
                    asymmetry_ceiling="",
                    asymmetry_reasoning="",
                    provider="",
                    model="",
                    tokens_in=0,
                    tokens_out=0,
                    cost_usd=Decimal("0"),
                ),
                db,
            )
            return {"status": "error", "error": str(e)}
