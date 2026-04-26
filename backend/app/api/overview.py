from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.overview import AllocationItem, OverviewSummary, PerformanceResponse
from app.services import overview as overview_service

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("/summary", response_model=OverviewSummary)
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_summary(db, current_user.id)


@router.get("/allocation", response_model=list[AllocationItem])
async def get_allocation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_allocation(db, current_user.id)


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(
    range: str = "1M",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_performance(db, current_user.id, range)
