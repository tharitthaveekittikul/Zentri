from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.encryption import decrypt, encrypt
from app.models.llm_settings import LLMSettings
from app.models.user import User
from app.services.hardware import detect_hardware

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/hardware")
async def hardware_info(_: User = Depends(get_current_user)):
    info = detect_hardware()
    return {
        "cpu_brand": info.cpu_brand,
        "ram_gb": round(info.ram_gb, 1),
        "is_apple_silicon": info.is_apple_silicon,
        "recommendation": info.recommendation,
    }


class LLMSettingsRequest(BaseModel):
    provider: str
    api_key: str | None = None
    model: str


class LLMSettingsResponse(BaseModel):
    id: str
    provider: str
    masked_key: str | None
    model: str
    is_active: bool


def _mask_key(plaintext: str | None) -> str | None:
    if not plaintext:
        return None
    return plaintext[:8] + "****"


@router.get("/llm", response_model=list[LLMSettingsResponse])
async def list_llm_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(LLMSettings))
    rows = result.scalars().all()
    return [
        LLMSettingsResponse(
            id=str(r.id),
            provider=r.provider,
            masked_key=_mask_key(decrypt(r.encrypted_api_key) if r.encrypted_api_key else None),
            model=r.model,
            is_active=r.is_active,
        )
        for r in rows
    ]


@router.put("/llm")
async def upsert_llm_settings(
    body: LLMSettingsRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    await db.execute(update(LLMSettings).values(is_active=False))
    result = await db.execute(
        select(LLMSettings).where(LLMSettings.provider == body.provider)
    )
    existing = result.scalar_one_or_none()
    encrypted = encrypt(body.api_key) if body.api_key else None
    if existing:
        existing.model = body.model
        if encrypted:
            existing.encrypted_api_key = encrypted
        existing.is_active = True
    else:
        db.add(LLMSettings(
            provider=body.provider,
            encrypted_api_key=encrypted,
            model=body.model,
            is_active=True,
        ))
    await db.commit()
    return {"ok": True}


@router.post("/test-llm")
async def test_llm_connection(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    import time
    from app.services.llm_service import get_llm_provider
    provider = await get_llm_provider(db)
    start = time.monotonic()
    try:
        resp = await provider.complete([{"role": "user", "content": "Reply with the single word: OK"}])
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"ok": True, "latency_ms": latency_ms, "response": resp.content[:50]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
