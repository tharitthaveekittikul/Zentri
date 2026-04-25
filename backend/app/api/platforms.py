import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.platform import PlatformCreate, PlatformResponse, PlatformUpdate
from app.services import platform as platform_service

router = APIRouter(prefix="/platforms", tags=["platforms"])


@router.post("", response_model=PlatformResponse, status_code=201)
async def create_platform(
    body: PlatformCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await platform_service.create_platform(
        db, current_user.id, body.name, body.asset_types_supported, body.notes
    )


@router.get("", response_model=list[PlatformResponse])
async def list_platforms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await platform_service.list_platforms(db, current_user.id)


@router.put("/{platform_id}", response_model=PlatformResponse)
async def update_platform(
    platform_id: uuid.UUID,
    body: PlatformUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    platform = await platform_service.get_platform(db, current_user.id, platform_id)
    if platform is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")
    return await platform_service.update_platform(db, platform, body.name, body.asset_types_supported, body.notes)


@router.delete("/{platform_id}", status_code=204)
async def delete_platform(
    platform_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    platform = await platform_service.get_platform(db, current_user.id, platform_id)
    if platform is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")
    await platform_service.delete_platform(db, platform)
    return Response(status_code=204)
