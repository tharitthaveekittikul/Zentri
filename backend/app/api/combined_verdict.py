from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.user import User
from app.services.combined_verdict import get_latest_combined_verdict

router = APIRouter(prefix="/analysis/combined-verdict", tags=["combined-verdict"])
logger = get_logger(__name__)


def _serialize(v) -> dict:
    return {
        "id": str(v.id),
        "asset_id": str(v.asset_id) if v.asset_id else None,
        "verdict": v.verdict,
        "conviction": v.conviction,
        "bull_thesis": v.bull_thesis,
        "bear_thesis": v.bear_thesis,
        "key_risks": v.key_risks,
        "reasoning": v.reasoning,
        "based_on": v.based_on,
        "provider": v.provider,
        "model": v.model,
        "tokens_in": v.tokens_in,
        "tokens_out": v.tokens_out,
        "cost_usd": float(v.cost_usd),
        "created_at": v.created_at.isoformat(),
        "status": v.status,
        "error_message": v.error_message,
    }


@router.get("/{symbol}/latest")
async def get_combined_verdict_latest(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verdict = await get_latest_combined_verdict(symbol, current_user.id, db)
    if not verdict:
        raise HTTPException(status_code=404, detail="No combined verdict found")
    return _serialize(verdict)


@router.post("/{symbol}", status_code=202)
async def trigger_combined_verdict(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == current_user.id)
    )
    if not asset_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    job_id = None
    try:
        from arq.connections import RedisSettings, create_pool
        from app.core.config import settings
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_run_combined_verdict", symbol.upper(), str(current_user.id))
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        pass

    logger.info("combined_verdict triggered symbol=%s user=%s job_id=%s", symbol, current_user.id, job_id)
    return {"symbol": symbol.upper(), "job_id": job_id}
