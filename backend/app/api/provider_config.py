import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.core.encryption import encrypt, decrypt
from app.core.logging import get_logger
from app.models.provider_config import ProviderConfig
from app.models.user import User
from app.schemas.provider_config import ProviderConfigCreate, ProviderConfigOut, ProviderConfigUpdate
from app.services.llm_gateway import _build_adapter

logger = get_logger(__name__)
router = APIRouter(prefix="/provider-configs", tags=["provider-configs"])


@router.get("", response_model=list[ProviderConfigOut])
async def list_provider_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("", response_model=ProviderConfigOut, status_code=status.HTTP_201_CREATED)
async def create_provider_config(
    body: ProviderConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    cfg = ProviderConfig(
        user_id=current_user.id,
        provider=body.provider,
        encrypted_api_key=encrypt(body.api_key) if body.api_key else None,
        host_url=body.host_url,
        created_at=now,
        updated_at=now,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    logger.info("ProviderConfig created: provider=%s user=%s", body.provider, current_user.id)
    return cfg


@router.patch("/{config_id}", response_model=ProviderConfigOut)
async def update_provider_config(
    config_id: uuid.UUID,
    body: ProviderConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    if body.api_key is not None:
        cfg.encrypted_api_key = encrypt(body.api_key)
    if body.host_url is not None:
        cfg.host_url = body.host_url
    cfg.is_connected = False
    await db.commit()
    await db.refresh(cfg)
    return cfg


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    await db.delete(cfg)
    await db.commit()


@router.post("/{config_id}/test-connection", response_model=ProviderConfigOut)
async def test_connection(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    api_key = decrypt(cfg.encrypted_api_key) if cfg.encrypted_api_key else None
    try:
        adapter = _build_adapter(cfg.provider, api_key, cfg.host_url)
        await adapter.fetch_models()
        cfg.is_connected = True
        logger.info("Provider connection OK: provider=%s user=%s", cfg.provider, current_user.id)
    except Exception as exc:
        cfg.is_connected = False
        logger.warning("Provider connection failed: provider=%s error=%s", cfg.provider, exc)
    await db.commit()
    await db.refresh(cfg)
    return cfg


@router.post("/{config_id}/fetch-models", response_model=ProviderConfigOut)
async def fetch_models(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    api_key = decrypt(cfg.encrypted_api_key) if cfg.encrypted_api_key else None
    try:
        adapter = _build_adapter(cfg.provider, api_key, cfg.host_url)
        models = await adapter.fetch_models()
        cfg.models_cache = models
        cfg.models_fetched_at = datetime.now(timezone.utc)
        cfg.is_connected = True
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {exc}")
    await db.commit()
    await db.refresh(cfg)
    return cfg


async def _get_own(db: AsyncSession, config_id: uuid.UUID, user_id: uuid.UUID) -> ProviderConfig:
    result = await db.execute(
        select(ProviderConfig).where(
            ProviderConfig.id == config_id,
            ProviderConfig.user_id == user_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Provider config not found")
    return cfg
