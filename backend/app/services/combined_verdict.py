from __future__ import annotations

import json
import uuid
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.combined_verdict import CombinedVerdict
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


def _section(label: str, text: str) -> str:
    return f"=== {label} ===\n{text}\n\n" if text else ""


async def run_combined_verdict(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> CombinedVerdict:
    from app.models.top_down_analysis import TopDownAnalysis
    from app.models.deep_dive_analysis import DeepDiveAnalysis
    from app.models.bear_case_analysis import BearCaseAnalysis
    from app.models.peer_comparison_analysis import PeerComparisonAnalysis

    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise ValueError(f"Asset {symbol} not found for user")

    # TopDownAnalysis has no user_id column — it is asset-scoped, not user-scoped
    td_row = await db.execute(
        select(TopDownAnalysis)
        .where(TopDownAnalysis.asset_id == asset.id)
        .order_by(desc(TopDownAnalysis.created_at)).limit(1)
    )
    top_down = td_row.scalar_one_or_none()

    dd_row = await db.execute(
        select(DeepDiveAnalysis)
        .where(DeepDiveAnalysis.asset_id == asset.id, DeepDiveAnalysis.user_id == user_id)
        .order_by(desc(DeepDiveAnalysis.created_at)).limit(1)
    )
    deep_dive = dd_row.scalar_one_or_none()

    pc_row = await db.execute(
        select(PeerComparisonAnalysis)
        .where(PeerComparisonAnalysis.asset_id == asset.id, PeerComparisonAnalysis.user_id == user_id)
        .order_by(desc(PeerComparisonAnalysis.created_at)).limit(1)
    )
    peer_comp = pc_row.scalar_one_or_none()

    bc_row = await db.execute(
        select(BearCaseAnalysis)
        .where(BearCaseAnalysis.asset_id == asset.id, BearCaseAnalysis.user_id == user_id)
        .order_by(desc(BearCaseAnalysis.created_at)).limit(1)
    )
    bear_case = bc_row.scalar_one_or_none()

    available = [
        name for name, val in [
            ("top_down_analysis", top_down),
            ("deep_dive", deep_dive),
            ("peer_comparison", peer_comp),
            ("bear_case", bear_case),
        ] if val is not None
    ]

    if not available:
        raise ValueError(f"Cannot run combined verdict for {symbol}: no analyses available")

    top_down_summary = _section(
        "TOP-DOWN ANALYSIS",
        f"Verdict: {top_down.verdict}\nMega Trend: {top_down.mega_trend}\nFinancial Health: {top_down.financial_health}"
    ) if top_down else ""

    deep_dive_summary = _section(
        "DEEP DIVE",
        f"Business Model: {deep_dive.business_model}\nMoat: {deep_dive.moat_edge_type} — {deep_dive.moat_summary}\nAsymmetry: {deep_dive.asymmetry_verdict}"
    ) if deep_dive else ""

    peer_comparison_summary = _section(
        "PEER COMPARISON",
        f"Sector: {peer_comp.sector_label}\nRanked: {json.dumps(peer_comp.ranked, indent=2)}"
    ) if peer_comp else ""

    bear_case_summary = _section(
        "BEAR CASE",
        f"Red Flags: {json.dumps(bear_case.red_flags, indent=2)}\nSummary: {bear_case.summary}"
    ) if bear_case else ""

    variables = {
        "symbol": symbol.upper(),
        "available_analyses": ", ".join(available),
        "top_down_summary": top_down_summary,
        "deep_dive_summary": deep_dive_summary,
        "peer_comparison_summary": peer_comparison_summary,
        "bear_case_summary": bear_case_summary,
    }

    gateway = LLMGateway(db)
    result = await gateway.complete("combined_verdict", user_id, variables)

    parsed = _parse_json(result.content)
    if not parsed:
        raise ValueError(f"LLM returned invalid JSON: {result.content[:200]}")

    verdict = CombinedVerdict(
        id=uuid.uuid4(),
        user_id=user_id,
        asset_id=asset.id,
        verdict=parsed.get("verdict", "hold"),
        conviction=int(parsed.get("conviction", 5)),
        bull_thesis=parsed.get("bull_thesis", ""),
        bear_thesis=parsed.get("bear_thesis", ""),
        key_risks=parsed.get("key_risks", []),
        reasoning=parsed.get("reasoning", ""),
        based_on=available,
        provider=result.provider,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=Decimal(str(result.cost_usd)),
    )
    db.add(verdict)
    await db.flush()
    logger.info("CombinedVerdict saved: user=%s symbol=%s verdict=%s conviction=%d",
                user_id, symbol, verdict.verdict, verdict.conviction)
    return verdict


async def get_latest_combined_verdict(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> CombinedVerdict | None:
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        return None
    result = await db.execute(
        select(CombinedVerdict)
        .where(CombinedVerdict.asset_id == asset.id, CombinedVerdict.user_id == user_id)
        .order_by(desc(CombinedVerdict.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
