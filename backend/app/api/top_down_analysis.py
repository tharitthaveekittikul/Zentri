import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.document import Document
from app.models.top_down_analysis import TopDownAnalysis
from app.models.user import User

router = APIRouter(prefix="/analysis/top-down", tags=["top-down-analysis"])
logger = get_logger(__name__)


def _serialize(a: TopDownAnalysis) -> dict:
    return {
        "id": str(a.id),
        "asset_id": str(a.asset_id) if a.asset_id else None,
        "mega_trend": a.mega_trend,
        "financial_health": a.financial_health,
        "swot": {
            "strengths": a.swot_strengths,
            "weaknesses": a.swot_weaknesses,
            "opportunities": a.swot_opportunities,
            "threats": a.swot_threats,
        },
        "verdict": a.verdict,
        "target_price": float(a.target_price) if a.target_price else None,
        "provider": a.provider,
        "model": a.model,
        "tokens_in": a.tokens_in,
        "tokens_out": a.tokens_out,
        "cost_usd": float(a.cost_usd),
        "ath_drop_pct": float(a.ath_drop_pct) if a.ath_drop_pct is not None else None,
        "created_at": a.created_at.isoformat(),
    }


@router.get("/all")
async def list_all_top_down(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TopDownAnalysis, Asset.symbol)
        .join(Asset, TopDownAnalysis.asset_id == Asset.id)
        .order_by(desc(TopDownAnalysis.created_at))
    )
    rows = result.all()

    seen: set = set()
    out = []
    for analysis, symbol in rows:
        if analysis.asset_id not in seen:
            seen.add(analysis.asset_id)
            out.append({
                "symbol": symbol,
                "verdict": analysis.verdict,
                "target_price": float(analysis.target_price) if analysis.target_price else None,
                "ath_drop_pct": float(analysis.ath_drop_pct) if analysis.ath_drop_pct is not None else None,
                "created_at": analysis.created_at.isoformat(),
            })
    return out


@router.post("/discover", status_code=202)
async def trigger_discover_top_down(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job_id = None
    try:
        from arq.connections import RedisSettings, create_pool
        from app.core.config import settings
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_discover_top_down", str(current_user.id))
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        pass
    logger.info("top_down_discovery triggered user=%s job_id=%s", current_user.id, job_id)
    return {"job_id": job_id}


@router.post("/{symbol}", status_code=202)
async def trigger_top_down_analysis(
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
        job = await redis.enqueue_job("job_run_top_down_analysis", symbol.upper())
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        pass

    logger.info("top_down_analysis triggered symbol=%s job_id=%s", symbol, job_id)
    return {"symbol": symbol.upper(), "job_id": job_id}


@router.get("/{symbol}/latest")
async def get_latest_top_down(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    a_result = await db.execute(
        select(TopDownAnalysis)
        .where(TopDownAnalysis.asset_id == asset.id)
        .order_by(desc(TopDownAnalysis.created_at))
        .limit(1)
    )
    analysis = a_result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="No top-down analysis found for this asset")

    d_result = await db.execute(
        select(Document)
        .where(Document.asset_id == asset.id)
        .order_by(desc(Document.created_at))
    )
    docs = d_result.scalars().all()

    serialized = _serialize(analysis)
    serialized["documents"] = [
        {
            "id": str(d.id),
            "filename": d.filename,
            "file_path": d.file_path,
            "doc_type": d.doc_type or "general",
            "source_url": d.source_url,
            "status": d.status,
        }
        for d in docs
        if d.status == "ready"
    ]
    return serialized


@router.get("/{symbol}/history")
async def get_top_down_history(
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
        select(TopDownAnalysis)
        .where(TopDownAnalysis.asset_id == asset.id)
        .order_by(desc(TopDownAnalysis.created_at))
        .limit(limit)
    )
    return [_serialize(a) for a in a_result.scalars().all()]
