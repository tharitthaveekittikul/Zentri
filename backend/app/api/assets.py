import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.price import Price
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetResponse
from app.schemas.price import PriceBar, PriceHistoryResponse
from app.services import asset as asset_service

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("", response_model=AssetResponse, status_code=201)
async def create_asset(
    body: AssetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await asset_service.create_asset(
        db, current_user.id, body.symbol, body.asset_type, body.name, body.currency, body.metadata_
    )


@router.get("", response_model=list[AssetResponse])
async def list_assets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await asset_service.get_all_assets(db, current_user.id)


@router.get("/search", response_model=list[AssetResponse])
async def search_assets(
    q: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await asset_service.search_assets(db, current_user.id, q)


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await asset_service.get_asset(db, current_user.id, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@router.get("/{asset_id}/prices", response_model=PriceHistoryResponse)
async def get_asset_price_history(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return OHLCV price history for an asset."""
    asset = await asset_service.get_asset(db, current_user.id, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    result = await db.execute(
        select(Price)
        .where(Price.asset_id == asset_id)
        .order_by(asc(Price.timestamp))
        .limit(500)
    )
    bars = list(result.scalars().all())
    return PriceHistoryResponse(asset_id=asset_id, bars=bars)
