import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.asset import Asset
from app.models.llm_conversation import LLMConversation
from app.models.user import User

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = get_logger(__name__)


@router.get("/usage/summary")
async def get_usage_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from datetime import datetime, timezone
    from sqlalchemy import func
    total = await db.execute(select(func.sum(AIAnalysis.cost_usd)))
    total_cost = float(total.scalar() or 0)

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly = await db.execute(
        select(func.sum(AIAnalysis.cost_usd)).where(AIAnalysis.created_at >= month_start)
    )
    monthly_cost = float(monthly.scalar() or 0)

    count = await db.execute(select(func.count(AIAnalysis.id)))
    total_analyses = int(count.scalar() or 0)

    by_provider = await db.execute(
        select(AIAnalysis.provider, func.sum(AIAnalysis.cost_usd).label("cost"))
        .group_by(AIAnalysis.provider)
    )
    return {
        "total_cost_usd": total_cost,
        "monthly_cost_usd": monthly_cost,
        "total_analyses": total_analyses,
        "by_provider": [{"provider": r.provider, "cost_usd": float(r.cost)} for r in by_provider],
    }


@router.get("/usage/logs")
async def get_usage_logs(
    limit: int = 100,
    provider: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(AIAnalysis).order_by(desc(AIAnalysis.created_at)).limit(limit)
    if provider:
        query = query.where(AIAnalysis.provider == provider)
    result = await db.execute(query)
    return [_serialize(a) for a in result.scalars().all()]


@router.get("/conversation/{analysis_id}")
async def get_conversation(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(LLMConversation)
        .where(LLMConversation.analysis_id == analysis_id)
        .order_by(LLMConversation.message_order)
    )
    msgs = result.scalars().all()
    if not msgs:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [{"role": m.role, "content": m.content, "order": m.message_order} for m in msgs]


@router.post("/{symbol}", status_code=202)
async def trigger_analysis(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    job_id = None
    try:
        from arq.connections import RedisSettings, create_pool
        from app.core.config import settings
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_run_analysis", symbol.upper())
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        pass
    logger.info("analysis triggered symbol=%s job_id=%s", symbol, job_id)
    return {"symbol": symbol.upper(), "job_id": job_id}


@router.get("/{symbol}/latest")
async def get_latest_verdict(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    a_result = await db.execute(
        select(AIAnalysis)
        .where(AIAnalysis.asset_id == asset.id)
        .order_by(desc(AIAnalysis.created_at))
        .limit(1)
    )
    analysis = a_result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this asset")
    return _serialize(analysis)


@router.get("/{symbol}/history")
async def get_analysis_history(
    symbol: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    a_result = await db.execute(
        select(AIAnalysis)
        .where(AIAnalysis.asset_id == asset.id)
        .order_by(desc(AIAnalysis.created_at))
        .limit(limit)
    )
    return [_serialize(a) for a in a_result.scalars().all()]


def _serialize(a: AIAnalysis) -> dict:
    return {
        "id": str(a.id),
        "asset_id": str(a.asset_id),
        "verdict": a.verdict,
        "target_price": float(a.target_price) if a.target_price else None,
        "reasoning": a.reasoning,
        "provider": a.provider,
        "model": a.model,
        "tokens_in": a.tokens_in,
        "tokens_out": a.tokens_out,
        "cost_usd": float(a.cost_usd),
        "created_at": a.created_at.isoformat(),
    }
