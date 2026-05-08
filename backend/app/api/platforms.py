import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.platform_config import PlatformConfig
from app.models.user import User

router = APIRouter(prefix="/platforms", tags=["platforms"])
logger = get_logger(__name__)

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class PlatformColorIn(BaseModel):
    color: str

    @field_validator("color")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        if not HEX_RE.match(v):
            raise ValueError("color must be a 6-digit hex string like #FF6B00")
        return v


class PlatformConfigOut(BaseModel):
    name: str
    color: str


@router.get("", response_model=list[PlatformConfigOut])
async def list_platform_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PlatformConfig)
        .where(PlatformConfig.user_id == current_user.id)
        .order_by(PlatformConfig.name)
    )
    rows = result.scalars().all()
    return [PlatformConfigOut(name=r.name, color=r.color) for r in rows]


@router.put("/{name}")
async def upsert_platform_color(
    name: str,
    body: PlatformColorIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        insert(PlatformConfig)
        .values(id=uuid.uuid4(), user_id=current_user.id, name=name, color=body.color)
        .on_conflict_do_update(
            constraint="uq_platform_configs_user_name",
            set_={"color": body.color},
        )
    )
    await db.execute(stmt)
    await db.commit()
    logger.info("upserted platform color user=%s name=%s color=%s", current_user.id, name, body.color)
    return {"ok": True}


@router.delete("/{name}", status_code=204)
async def delete_platform_color(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        delete(PlatformConfig)
        .where(PlatformConfig.user_id == current_user.id, PlatformConfig.name == name)
        .returning(PlatformConfig.id)
    )
    if result.fetchone() is None:
        raise HTTPException(status_code=404, detail="Platform config not found")
    await db.commit()
