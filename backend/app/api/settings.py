from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.encryption import decrypt, encrypt
from app.core.logging import get_logger
from app.models.llm_settings import LLMSettings
from app.models.user import User
from app.services import exchange_rate as exchange_rate_service
from app.services.hardware import detect_hardware
from app.services.telegram import send_message as _send_telegram
from app.services.user_context import get_user_age_context

router = APIRouter(prefix="/settings", tags=["settings"])
logger = get_logger(__name__)


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


class DisplaySettingsOut(BaseModel):
    currency_primary: str
    currency_secondary: str


class DisplaySettingsIn(BaseModel):
    currency_primary: str
    currency_secondary: str


@router.get("/display", response_model=DisplaySettingsOut)
async def get_display_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return DisplaySettingsOut(
        currency_primary=current_user.currency_primary,
        currency_secondary=current_user.currency_secondary,
    )


@router.patch("/display", response_model=DisplaySettingsOut)
async def update_display_settings(
    body: DisplaySettingsIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.currency_primary = body.currency_primary
    current_user.currency_secondary = body.currency_secondary
    await db.commit()
    await db.refresh(current_user)
    return DisplaySettingsOut(
        currency_primary=current_user.currency_primary,
        currency_secondary=current_user.currency_secondary,
    )


class ProfileSettingsIn(BaseModel):
    birth_date: date_type | None = None
    plan_to_age: int | None = None


class ProfileSettingsOut(BaseModel):
    birth_date: date_type | None
    plan_to_age: int | None
    current_age: int | None
    years_remaining: int | None
    target_year: int | None


@router.get("/profile", response_model=ProfileSettingsOut)
async def get_profile_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctx = get_user_age_context(current_user)
    return ProfileSettingsOut(
        birth_date=current_user.birth_date,
        plan_to_age=current_user.plan_to_age,
        current_age=ctx["current_age"] if ctx else None,
        years_remaining=ctx["years_remaining"] if ctx else None,
        target_year=ctx["target_year"] if ctx else None,
    )


@router.patch("/profile", response_model=ProfileSettingsOut)
async def update_profile_settings(
    body: ProfileSettingsIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if "birth_date" in body.model_fields_set:
        current_user.birth_date = body.birth_date
    if "plan_to_age" in body.model_fields_set:
        current_user.plan_to_age = body.plan_to_age
    await db.commit()
    await db.refresh(current_user)
    ctx = get_user_age_context(current_user)
    return ProfileSettingsOut(
        birth_date=current_user.birth_date,
        plan_to_age=current_user.plan_to_age,
        current_age=ctx["current_age"] if ctx else None,
        years_remaining=ctx["years_remaining"] if ctx else None,
        target_year=ctx["target_year"] if ctx else None,
    )


class TelegramConfigIn(BaseModel):
    bot_token: str | None = None
    chat_id: str


class TelegramConfigOut(BaseModel):
    chat_id: str | None
    has_token: bool


@router.get("/telegram", response_model=TelegramConfigOut)
async def get_telegram_config(
    current_user: User = Depends(get_current_user),
):
    return TelegramConfigOut(
        chat_id=current_user.telegram_chat_id,
        has_token=bool(current_user.telegram_bot_token),
    )


@router.put("/telegram", response_model=TelegramConfigOut)
async def save_telegram_config(
    body: TelegramConfigIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.bot_token:
        current_user.telegram_bot_token = encrypt(body.bot_token)
    current_user.telegram_chat_id = body.chat_id
    await db.commit()
    return TelegramConfigOut(chat_id=body.chat_id, has_token=True)


@router.post("/telegram/test")
async def test_telegram(
    current_user: User = Depends(get_current_user),
):
    if not current_user.telegram_bot_token or not current_user.telegram_chat_id:
        raise HTTPException(
            status_code=400,
            detail="Telegram not configured — save bot_token and chat_id first",
        )
    try:
        bot_token = decrypt(current_user.telegram_bot_token)
        await _send_telegram(
            bot_token,
            current_user.telegram_chat_id,
            "✅ <b>Zentri</b> — Test message received! Price alerts are configured correctly.",
        )
    except Exception as exc:
        logger.exception("test_telegram failed: %s", exc)
        raise HTTPException(status_code=502, detail="Telegram delivery failed — check bot token and chat ID")
    return {"ok": True}


class SecApiConfigIn(BaseModel):
    api_key: str


class SecApiConfigOut(BaseModel):
    has_key: bool


@router.get("/sec-api", response_model=SecApiConfigOut)
async def get_sec_api_config(
    current_user: User = Depends(get_current_user),
):
    return SecApiConfigOut(has_key=bool(current_user.sec_api_key))


@router.put("/sec-api", response_model=SecApiConfigOut)
async def save_sec_api_config(
    body: SecApiConfigIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.sec_api_key = encrypt(body.api_key)
    await db.commit()
    return SecApiConfigOut(has_key=True)


@router.delete("/sec-api", status_code=204)
async def delete_sec_api_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.sec_api_key = None
    await db.commit()


class PrivacySettingsOut(BaseModel):
    privacy_mode: bool


class PrivacySettingsIn(BaseModel):
    privacy_mode: bool


@router.get("/privacy", response_model=PrivacySettingsOut)
async def get_privacy_settings(
    current_user: User = Depends(get_current_user),
):
    return PrivacySettingsOut(privacy_mode=current_user.privacy_mode)


@router.patch("/privacy", response_model=PrivacySettingsOut)
async def update_privacy_settings(
    body: PrivacySettingsIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.privacy_mode = body.privacy_mode
    await db.commit()
    await db.refresh(current_user)
    return PrivacySettingsOut(privacy_mode=current_user.privacy_mode)


@router.get("/exchange-rate")
async def get_exchange_rate(
    from_currency: str,
    to_currency: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rate = await exchange_rate_service.get_rate(db, from_currency, to_currency)
    if rate is None:
        raise HTTPException(status_code=503, detail="Exchange rate unavailable")
    return {"from": from_currency, "to": to_currency, "rate": str(rate)}
