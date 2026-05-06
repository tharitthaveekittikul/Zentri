import asyncio
import json
import uuid
from datetime import date, datetime, timezone

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.user import User
from app.schemas.ipo import IpoAnalysisResult
from app.services import ipo_feed
from app.services.llm_gateway import LLMGateway

logger = get_logger(__name__)
router = APIRouter(prefix="/ipos", tags=["ipos"])


async def _get_cached_analysis(db: AsyncSession, ipo_event_id: uuid.UUID) -> AIAnalysis | None:
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    result = await db.execute(
        select(AIAnalysis).where(
            AIAnalysis.ipo_event_id == ipo_event_id,
            AIAnalysis.created_at >= today_start,
        )
    )
    return result.scalars().first()


@router.post("/{event_id}/analyze", response_model=IpoAnalysisResult)
async def analyze_ipo(
    event_id: uuid.UUID,
    force: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await ipo_feed.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="IPO event not found")

    if not force:
        cached = await _get_cached_analysis(db, event_id)
        if cached:
            return IpoAnalysisResult(
                verdict=cached.verdict,
                suggested_price=cached.target_price,
                reasoning=cached.reasoning,
                provider=cached.provider,
                model=cached.model,
                cached=True,
            )

    try:
        info = await asyncio.get_event_loop().run_in_executor(
            None, lambda: yf.Ticker(event.symbol).info
        )
    except Exception:
        info = {}

    variables = {
        "symbol": event.symbol,
        "company_name": event.company_name or "N/A",
        "sector": event.sector or "N/A",
        "ipo_date": str(event.ipo_date),
        "price_low": str(event.price_low) if event.price_low else "N/A",
        "price_high": str(event.price_high) if event.price_high else "N/A",
        "description": (info.get("longBusinessSummary", "N/A") or "N/A")[:500],
        "market_cap": str(info.get("marketCap", "N/A")),
        "pe_ratio": str(info.get("trailingPE", "N/A")),
    }

    try:
        gateway = LLMGateway(db)
        result = await gateway.complete("ipo_analysis", current_user.id, variables)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="LLM not configured for IPO analysis. Please assign a model in Settings → AI & LLM.",
        ) from exc

    try:
        parsed = json.loads(result.content)
        verdict = parsed.get("verdict", "WATCH")
        suggested_price = parsed.get("suggested_price")
        reasoning = parsed.get("reasoning", result.content)
    except (json.JSONDecodeError, AttributeError):
        verdict = "WATCH"
        suggested_price = None
        reasoning = result.content

    analysis = AIAnalysis(
        ipo_event_id=event_id,
        verdict=verdict,
        target_price=suggested_price,
        reasoning=reasoning,
        provider=result.provider,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
    )
    db.add(analysis)
    await db.commit()
    logger.info("IPO analysis stored: event=%s verdict=%s", event_id, verdict)

    return IpoAnalysisResult(
        verdict=verdict,
        suggested_price=suggested_price,
        reasoning=reasoning,
        provider=result.provider,
        model=result.model,
        cached=False,
    )
