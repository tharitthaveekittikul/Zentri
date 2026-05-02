import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.feature_llm_config import FeatureLLMConfig, FEATURE_KEYS
from app.models.user import User
from app.schemas.feature_llm_config import FeatureLLMConfigCreate, FeatureLLMConfigOut, FeatureLLMConfigUpdate
from app.services.llm_gateway import DEFAULT_SYSTEM_PROMPTS

logger = get_logger(__name__)
router = APIRouter(prefix="/feature-llm-configs", tags=["feature-llm-configs"])


@router.get("", response_model=list[FeatureLLMConfigOut])
async def list_feature_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FeatureLLMConfig).where(FeatureLLMConfig.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("", response_model=FeatureLLMConfigOut, status_code=status.HTTP_201_CREATED)
async def create_feature_config(
    body: FeatureLLMConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.feature_key not in FEATURE_KEYS:
        raise HTTPException(status_code=422, detail=f"Unknown feature_key: {body.feature_key}")
    system_prompt = body.system_prompt or DEFAULT_SYSTEM_PROMPTS[body.feature_key]
    is_customized = body.system_prompt is not None
    now = datetime.now(timezone.utc)
    cfg = FeatureLLMConfig(
        user_id=current_user.id,
        feature_key=body.feature_key,
        provider_config_id=body.provider_config_id,
        model=body.model,
        system_prompt=system_prompt,
        is_prompt_customized=is_customized,
        created_at=now,
        updated_at=now,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    logger.info("FeatureLLMConfig created: key=%s user=%s", body.feature_key, current_user.id)
    return cfg


@router.patch("/{config_id}", response_model=FeatureLLMConfigOut)
async def update_feature_config(
    config_id: uuid.UUID,
    body: FeatureLLMConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    if body.provider_config_id is not None:
        cfg.provider_config_id = body.provider_config_id
    if body.model is not None:
        cfg.model = body.model
    if body.system_prompt is not None:
        cfg.system_prompt = body.system_prompt
        cfg.is_prompt_customized = True
    await db.commit()
    await db.refresh(cfg)
    return cfg


@router.post("/{config_id}/reset-prompt", response_model=FeatureLLMConfigOut)
async def reset_prompt(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    cfg.system_prompt = DEFAULT_SYSTEM_PROMPTS[cfg.feature_key]
    cfg.is_prompt_customized = False
    await db.commit()
    await db.refresh(cfg)
    logger.info("System prompt reset to default: key=%s user=%s", cfg.feature_key, current_user.id)
    return cfg


async def _get_own(db: AsyncSession, config_id: uuid.UUID, user_id: uuid.UUID) -> FeatureLLMConfig:
    result = await db.execute(
        select(FeatureLLMConfig).where(
            FeatureLLMConfig.id == config_id,
            FeatureLLMConfig.user_id == user_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Feature LLM config not found")
    return cfg
