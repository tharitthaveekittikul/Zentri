from __future__ import annotations

import json
import uuid
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.deep_dive_analysis import DeepDiveAnalysis
from app.services.llm_gateway import LLMGateway

logger = get_logger(__name__)


def _parse_json(content: str) -> dict | None:
    try:
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except (json.JSONDecodeError, IndexError):
        return None


async def run_deep_dive(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> DeepDiveAnalysis:
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise ValueError(f"Asset {symbol} not found for user")

    variables = {
        "symbol": symbol.upper(),
        "company_name": asset.name,
        "sector": asset.metadata_.get("sector", "Unknown"),
    }

    gateway = LLMGateway(db)
    result = await gateway.complete("deep_dive", user_id, variables)

    parsed = _parse_json(result.content)
    if not parsed:
        raise ValueError(f"LLM returned invalid JSON: {result.content[:200]}")

    moat = parsed.get("moat", {})
    asym = parsed.get("asymmetry", {})

    analysis = DeepDiveAnalysis(
        id=uuid.uuid4(),
        user_id=user_id,
        asset_id=asset.id,
        business_model=parsed.get("business_model", ""),
        moat_edge_type=moat.get("edge_type", "none"),
        moat_summary=moat.get("summary", ""),
        moat_competitors=moat.get("competitors", []),
        catalysts=parsed.get("catalysts", []),
        asymmetry_verdict=asym.get("verdict", "mixed"),
        asymmetry_floor=asym.get("floor", ""),
        asymmetry_ceiling=asym.get("ceiling", ""),
        asymmetry_reasoning=asym.get("reasoning", ""),
        provider=result.provider,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=Decimal(str(result.cost_usd)),
    )
    db.add(analysis)
    await db.flush()
    logger.info("DeepDiveAnalysis saved: user=%s symbol=%s", user_id, symbol)
    return analysis


async def get_latest_deep_dive(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> DeepDiveAnalysis | None:
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        return None
    result = await db.execute(
        select(DeepDiveAnalysis)
        .where(DeepDiveAnalysis.asset_id == asset.id, DeepDiveAnalysis.user_id == user_id)
        .order_by(desc(DeepDiveAnalysis.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
