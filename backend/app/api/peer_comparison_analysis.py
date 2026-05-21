from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.user import User
from app.services.peer_comparison_analysis import get_latest_peer_comparison

router = APIRouter(prefix="/analysis/peer-comparison", tags=["peer-comparison"])
logger = get_logger(__name__)


def _serialize(a) -> dict:
    return {
        "id": str(a.id),
        "asset_id": str(a.asset_id) if a.asset_id else None,
        "sector_label": a.sector_label,
        "ranked": a.ranked,
        "methodology_note": a.methodology_note,
        "provider": a.provider,
        "model": a.model,
        "tokens_in": a.tokens_in,
        "tokens_out": a.tokens_out,
        "cost_usd": float(a.cost_usd),
        "created_at": a.created_at.isoformat(),
        "status": a.status,
        "error_message": a.error_message,
    }


@router.get("/{symbol}/latest")
async def get_peer_comparison_latest(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = await get_latest_peer_comparison(symbol, current_user.id, db)
    if not analysis:
        raise HTTPException(status_code=404, detail="No peer comparison found")
    return _serialize(analysis)


@router.post("/{symbol}", status_code=202)
async def trigger_peer_comparison(
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
        job = await redis.enqueue_job("job_run_peer_comparison", symbol.upper(), str(current_user.id))
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        pass

    logger.info("peer_comparison triggered symbol=%s user=%s job_id=%s", symbol, current_user.id, job_id)
    return {"symbol": symbol.upper(), "job_id": job_id}
