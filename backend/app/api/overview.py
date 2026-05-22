from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.overview import AllocationItem, NetWorthPoint, OverviewSummary, PerformanceResponse, SectorAllocationItem
from app.services import overview as overview_service
from app.services.overview_analysis import (
    get_latest_overview_analysis,
    is_cooldown_active,
    run_overview_analysis,
)

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("/summary", response_model=OverviewSummary)
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_summary(db, current_user.id, current_user.currency_primary)


@router.get("/allocation/sector", response_model=list[SectorAllocationItem])
async def get_sector_allocation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_sector_allocation(db, current_user.id, current_user.currency_primary)


@router.get("/allocation", response_model=list[AllocationItem])
async def get_allocation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_allocation(db, current_user.id, current_user.currency_primary)


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(
    range: str = "1M",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_performance(db, current_user.id, range)


@router.get("/net-worth", response_model=list[NetWorthPoint])
async def get_net_worth_timeline(
    range: str = "1M",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_net_worth_timeline(db, current_user.id, range)


@router.get("/ai-analysis/latest")
async def get_latest_ai_analysis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis = await get_latest_overview_analysis(db, current_user.id)
    if not analysis:
        return None
    return _serialize_analysis(analysis)


@router.post("/ai-analysis")
async def trigger_ai_analysis(
    force: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not force:
        latest = await get_latest_overview_analysis(db, current_user.id)
        if is_cooldown_active(latest):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "cooldown_active",
                    "message": "Analysis was run recently. Pass ?force=true to override.",
                    "last_analysis": _serialize_analysis(latest),
                },
            )
    analysis = await run_overview_analysis(db, current_user.id)
    await db.commit()
    return _serialize_analysis(analysis)


def _serialize_analysis(a) -> dict:
    return {
        "id": str(a.id),
        "score": a.score,
        "grade": a.grade,
        "health": a.health,
        "portfolio_adherence_pct": a.portfolio_adherence_pct,
        "insights": a.insights,
        "top_action": a.top_action,
        "provider": a.provider,
        "model": a.model,
        "tokens_in": a.tokens_in,
        "tokens_out": a.tokens_out,
        "cost_usd": float(a.cost_usd),
        "cost_thb": float(a.cost_thb),
        "created_at": a.created_at.isoformat(),
    }
