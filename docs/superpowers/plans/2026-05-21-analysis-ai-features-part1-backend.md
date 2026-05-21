# Analysis AI Features — Part 1: Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Deep Dive, Peer Comparison, Bear Case, and Combined Verdict analysis features to the backend — including DB models, services, API routers, ARQ worker jobs, and all feature key registrations.

**Architecture:** Each feature is a separate module (model + service + API + worker job) following the existing `top_down_analysis` pattern. All LLM calls go through `LLMGateway.complete()` which auto-logs to `LLMCallLog`. New features are per-user (pass `user_id` to ARQ job and filter results by it).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL/TimescaleDB, ARQ (Redis), yfinance, Alembic

**Spec:** `docs/superpowers/specs/2026-05-21-analysis-ai-features-design.md`
**Part 2:** `docs/superpowers/plans/2026-05-21-analysis-ai-features-part2-frontend.md`

---

## File Map

**Create:**
- `backend/app/models/deep_dive_analysis.py`
- `backend/app/models/bear_case_analysis.py`
- `backend/app/models/peer_comparison_analysis.py`
- `backend/app/models/combined_verdict.py`
- `backend/app/services/deep_dive_analysis.py`
- `backend/app/services/bear_case_analysis.py`
- `backend/app/services/peer_comparison_analysis.py`
- `backend/app/services/combined_verdict.py`
- `backend/app/api/deep_dive_analysis.py`
- `backend/app/api/bear_case_analysis.py`
- `backend/app/api/peer_comparison_analysis.py`
- `backend/app/api/combined_verdict.py`
- `backend/worker/jobs/run_deep_dive.py`
- `backend/worker/jobs/run_bear_case.py`
- `backend/worker/jobs/run_peer_comparison.py`
- `backend/worker/jobs/run_combined_verdict.py`
- `backend/alembic/versions/041_add_analysis_ai_features.py`
- `backend/tests/test_deep_dive.py`
- `backend/tests/test_bear_case.py`
- `backend/tests/test_peer_comparison.py`
- `backend/tests/test_combined_verdict.py`

**Modify:**
- `backend/app/models/feature_llm_config.py` — add 4 keys to `FEATURE_KEYS`
- `backend/app/services/llm_gateway.py` — add prompts + keys for 4 features
- `backend/app/main.py` — register 4 new routers
- `backend/worker/main.py` — register 4 new job functions

---

## Task 1: Register all 4 feature keys (5 locations)

**Files:**
- Modify: `backend/app/models/feature_llm_config.py`
- Modify: `backend/app/services/llm_gateway.py`

**⚠️ CRITICAL:** All 5 locations must be updated or the feature silently breaks. Missing from backend model → 422 error on config creation. Missing from gateway dicts → KeyError crash at runtime.

- [ ] **Step 1: Add keys to `feature_llm_config.py`**

In `backend/app/models/feature_llm_config.py`, extend the tuple:

```python
FEATURE_KEYS = (
    "import_translator",
    "portfolio_analysis",
    "overview_analysis",
    "chat",
    "watchlist_scan",
    "watchlist_discovery",
    "ipo_analysis",
    "top_down_analysis",
    "top_down_discovery",
    "deep_dive",
    "peer_comparison",
    "bear_case",
    "combined_verdict",
)
```

- [ ] **Step 2: Add keys and prompts to `llm_gateway.py`**

In `backend/app/services/llm_gateway.py`:

2a. Add to `FEATURE_KEYS` tuple (same 4 keys as above).

2b. Add to `DEFAULT_SYSTEM_PROMPTS` dict:

```python
"deep_dive": (
    "You are a senior equity analyst specializing in business model assessment. "
    "You provide clear, structured company breakdowns focused on fundamentals and competitive positioning. "
    "Always respond with valid JSON matching the specified schema exactly. No markdown, no explanation outside JSON."
),
"peer_comparison": (
    "You are a quantitative equity analyst specializing in relative valuation. "
    "You build precise peer comparison tables using financial data to identify the best value/growth opportunities. "
    "Always respond with valid JSON matching the specified schema exactly. No markdown, no explanation outside JSON."
),
"bear_case": (
    "You are a skeptical short-seller conducting fundamental risk analysis. "
    "You identify the most serious structural and financial red flags, citing data where available. "
    "Always respond with valid JSON matching the specified schema exactly. No markdown, no explanation outside JSON."
),
"combined_verdict": (
    "You are a chief investment officer synthesizing multiple research reports into a final investment verdict. "
    "You weigh evidence from all available analyses and provide a clear, actionable recommendation. "
    "Always respond with valid JSON matching the specified schema exactly. No markdown, no explanation outside JSON."
),
```

2c. Add to `SYSTEM_PROMPTS` dict (same values as `DEFAULT_SYSTEM_PROMPTS` above).

2d. Add to `HUMAN_PROMPTS` dict:

```python
"deep_dive": (
    "Analyze {company_name} ({symbol}) in the {sector} sector.\n"
    "Current date: {current_date}\n\n"
    "Provide a 4-part deep dive:\n"
    "1. Business Model: How do they actually make money? Core product in plain English.\n"
    "2. Moat: Top 3 competitors. Does {symbol} have a durable edge "
    "(patent, switching_cost, network_effect, cost_structure) that rivals can't copy?\n"
    "3. Catalysts: Upcoming launches, earnings, regulatory events, or partnerships in the next 12 months.\n"
    "4. Asymmetry: Is there a low valuation floor vs high growth ceiling? Why or why not?\n\n"
    'Respond ONLY with this JSON:\n'
    '{{\n'
    '  "business_model": "...",\n'
    '  "moat": {{"edge_type": "patent|switching_cost|network_effect|cost_structure|none", '
    '"summary": "...", "competitors": ["T1", "T2", "T3"]}},\n'
    '  "catalysts": [{{"title": "...", "timeframe": "...", "impact": "high|medium|low"}}],\n'
    '  "asymmetry": {{"verdict": "yes|no|mixed", "floor": "...", "ceiling": "...", "reasoning": "..."}}\n'
    '}}'
),
"peer_comparison": (
    "Analyze {symbol} ({sector}) relative to its peers using this financial data:\n\n"
    "{financial_table}\n\n"
    "Current date: {current_date}\n\n"
    "Value/Growth Score = P/S TTM ÷ YoY Revenue Growth %. Lower = better.\n"
    'Label: "BEST" for lowest score, "AVOID" for highest, "FAIR" for all others.\n\n'
    'Respond ONLY with this JSON:\n'
    '{{\n'
    '  "sector_label": "...",\n'
    '  "methodology_note": "Value/Growth Score = P/S TTM / YoY Revenue Growth %",\n'
    '  "ranked": [\n'
    '    {{"ticker": "...", "company_name": "...", "ps_ttm": 0.0, "ps_forward": 0.0,\n'
    '      "ev_ebitda": 0.0, "gross_margin_pct": 0.0, "yoy_revenue_growth_pct": 0.0,\n'
    '      "revenue_trend": "Reaccelerating|Accelerating|Stable|Decelerating|Declining",\n'
    '      "value_growth_score": 0.00, "label": "BEST|FAIR|AVOID", "notes": "..."}}\n'
    '  ]\n'
    '}}'
),
"bear_case": (
    "Conduct a bear case analysis for {company_name} ({symbol}) in the {sector} sector.\n"
    "Current date: {current_date}\n\n"
    "Financial data (yfinance):\n"
    "- Gross margins last 4 quarters: {gross_margins_4q}\n"
    "- YoY revenue growth: {revenue_growth_yoy}%\n"
    "- Operating margin: {operating_margin}%\n"
    "- Debt/Equity ratio: {debt_equity}\n"
    "- Short interest: {short_interest_pct}%\n\n"
    "Identify the 3 most serious red flags ranked by severity.\n"
    'Mark data_source "yfinance" if supported by data above, "llm_knowledge" otherwise.\n\n'
    'Respond ONLY with this JSON:\n'
    '{{\n'
    '  "red_flags": [\n'
    '    {{"rank": 1, "title": "...", "severity": "high|medium|low",\n'
    '      "data_source": "yfinance|llm_knowledge", "evidence": "...", "detail": "..."}}\n'
    '  ],\n'
    '  "summary": "..."\n'
    '}}'
),
"combined_verdict": (
    "Synthesize the following research on {symbol} into a final verdict.\n"
    "Current date: {current_date}\n"
    "Available analyses: {available_analyses}\n\n"
    "{top_down_summary}"
    "{deep_dive_summary}"
    "{peer_comparison_summary}"
    "{bear_case_summary}"
    "\nProvide a final investment verdict.\n\n"
    'Respond ONLY with this JSON:\n'
    '{{\n'
    '  "verdict": "strong_buy|buy|hold|sell|strong_sell",\n'
    '  "conviction": 7,\n'
    '  "bull_thesis": "...",\n'
    '  "bear_thesis": "...",\n'
    '  "key_risks": ["...", "..."],\n'
    '  "reasoning": "...",\n'
    '  "based_on": ["top_down_analysis", "deep_dive"]\n'
    '}}'
),
```

- [ ] **Step 3: Verify no KeyError at import time**

```bash
cd backend && python -c "from app.services.llm_gateway import DEFAULT_SYSTEM_PROMPTS, SYSTEM_PROMPTS, HUMAN_PROMPTS; print([k for k in ['deep_dive','peer_comparison','bear_case','combined_verdict'] if k not in DEFAULT_SYSTEM_PROMPTS])"
```

Expected: `[]`

---

## Task 2: Alembic migration — 4 new tables

**Files:**
- Create: `backend/alembic/versions/041_add_analysis_ai_features.py`

- [ ] **Step 1: Verify latest migration is 040**

```bash
cd backend && ls alembic/versions/ | sort | tail -3
```

Expected: last line is `040_add_content_hash.py`

- [ ] **Step 2: Create migration file**

```python
"""add analysis ai feature tables

Revision ID: 041
Revises: 040
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deep_dive_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", sa.String, nullable=True),
        sa.Column("business_model", sa.Text, nullable=False),
        sa.Column("moat_edge_type", sa.String(50), nullable=False),
        sa.Column("moat_summary", sa.Text, nullable=False),
        sa.Column("moat_competitors", postgresql.JSON, nullable=False),
        sa.Column("catalysts", postgresql.JSON, nullable=False),
        sa.Column("asymmetry_verdict", sa.String(20), nullable=False),
        sa.Column("asymmetry_floor", sa.Text, nullable=False),
        sa.Column("asymmetry_ceiling", sa.Text, nullable=False),
        sa.Column("asymmetry_reasoning", sa.Text, nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "bear_case_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", sa.String, nullable=True),
        sa.Column("red_flags", postgresql.JSON, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "peer_comparison_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", sa.String, nullable=True),
        sa.Column("sector_label", sa.String(100), nullable=False),
        sa.Column("ranked", postgresql.JSON, nullable=False),
        sa.Column("methodology_note", sa.Text, nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "combined_verdicts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", sa.String, nullable=True),
        sa.Column("verdict", sa.String(20), nullable=False),
        sa.Column("conviction", sa.Integer, nullable=False),
        sa.Column("bull_thesis", sa.Text, nullable=False),
        sa.Column("bear_thesis", sa.Text, nullable=False),
        sa.Column("key_risks", postgresql.JSON, nullable=False),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("based_on", postgresql.JSON, nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("combined_verdicts")
    op.drop_table("peer_comparison_analyses")
    op.drop_table("bear_case_analyses")
    op.drop_table("deep_dive_analyses")
```

- [ ] **Step 3: Run migration**

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade 040 -> 041`

---

## Task 3: Deep Dive backend (model + service + API + worker job)

**Files:**
- Create: `backend/app/models/deep_dive_analysis.py`
- Create: `backend/app/services/deep_dive_analysis.py`
- Create: `backend/app/api/deep_dive_analysis.py`
- Create: `backend/worker/jobs/run_deep_dive.py`
- Create: `backend/tests/test_deep_dive.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_deep_dive.py
import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


VALID_RESPONSE = json.dumps({
    "business_model": "AMD designs CPUs and GPUs, licensing IP and selling chips.",
    "moat": {
        "edge_type": "switching_cost",
        "summary": "x86 architecture lock-in across enterprise.",
        "competitors": ["NVDA", "INTC", "QCOM"],
    },
    "catalysts": [
        {"title": "MI300X ramp", "timeframe": "H1 2025", "impact": "high"}
    ],
    "asymmetry": {
        "verdict": "yes",
        "floor": "CPU segment provides downside protection at ~5x P/S",
        "ceiling": "AI GPU TAM expansion to $400B by 2027",
        "reasoning": "Asymmetric upside from data center GPU share gains.",
    },
})


@pytest.mark.asyncio
async def test_run_deep_dive_saves_analysis():
    from app.services.deep_dive_analysis import run_deep_dive
    from app.services.llm_gateway import LLMGatewayResult

    mock_db = AsyncMock()
    mock_asset = MagicMock()
    mock_asset.id = uuid.uuid4()
    mock_asset.name = "Advanced Micro Devices"
    mock_asset.metadata_ = {"sector": "Technology"}

    mock_result_row = MagicMock()
    mock_result_row.scalar_one_or_none.return_value = mock_asset
    mock_db.execute = AsyncMock(return_value=mock_result_row)

    gateway_result = LLMGatewayResult(
        content=VALID_RESPONSE,
        prompt="test",
        tokens_in=100,
        tokens_out=200,
        cost_usd=0.001,
        cost_thb=0.035,
        exchange_rate=35.0,
        model="claude-3-5-sonnet",
        provider="anthropic",
    )

    with patch("app.services.deep_dive_analysis.LLMGateway") as MockGateway:
        mock_gw = AsyncMock()
        mock_gw.complete = AsyncMock(return_value=gateway_result)
        MockGateway.return_value = mock_gw

        analysis = await run_deep_dive("AMD", uuid.uuid4(), mock_db)

    assert analysis.business_model == "AMD designs CPUs and GPUs, licensing IP and selling chips."
    assert analysis.moat_edge_type == "switching_cost"
    assert analysis.moat_competitors == ["NVDA", "INTC", "QCOM"]
    assert analysis.asymmetry_verdict == "yes"
    assert analysis.provider == "anthropic"
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_run_deep_dive_raises_if_asset_not_found():
    from app.services.deep_dive_analysis import run_deep_dive

    mock_db = AsyncMock()
    mock_result_row = MagicMock()
    mock_result_row.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result_row)

    with pytest.raises(ValueError, match="not found"):
        await run_deep_dive("FAKE", uuid.uuid4(), mock_db)
```

- [ ] **Step 2: Run test — confirm fails**

```bash
cd backend && python -m pytest tests/test_deep_dive.py -v 2>&1 | head -20
```

Expected: `ImportError` or `ModuleNotFoundError` (file doesn't exist yet).

- [ ] **Step 3: Create model**

```python
# backend/app/models/deep_dive_analysis.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeepDiveAnalysis(Base):
    __tablename__ = "deep_dive_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)

    business_model: Mapped[str] = mapped_column(Text, nullable=False)
    moat_edge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    moat_summary: Mapped[str] = mapped_column(Text, nullable=False)
    moat_competitors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    catalysts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    asymmetry_verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    asymmetry_floor: Mapped[str] = mapped_column(Text, nullable=False)
    asymmetry_ceiling: Mapped[str] = mapped_column(Text, nullable=False)
    asymmetry_reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 4: Create service**

```python
# backend/app/services/deep_dive_analysis.py
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
```

- [ ] **Step 5: Create API router**

```python
# backend/app/api/deep_dive_analysis.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.user import User
from app.services.deep_dive_analysis import get_latest_deep_dive
from sqlalchemy import select

router = APIRouter(prefix="/analysis/deep-dive", tags=["deep-dive"])
logger = get_logger(__name__)


def _serialize(a) -> dict:
    return {
        "id": str(a.id),
        "asset_id": str(a.asset_id) if a.asset_id else None,
        "business_model": a.business_model,
        "moat": {
            "edge_type": a.moat_edge_type,
            "summary": a.moat_summary,
            "competitors": a.moat_competitors,
        },
        "catalysts": a.catalysts,
        "asymmetry": {
            "verdict": a.asymmetry_verdict,
            "floor": a.asymmetry_floor,
            "ceiling": a.asymmetry_ceiling,
            "reasoning": a.asymmetry_reasoning,
        },
        "provider": a.provider,
        "model": a.model,
        "tokens_in": a.tokens_in,
        "tokens_out": a.tokens_out,
        "cost_usd": float(a.cost_usd),
        "created_at": a.created_at.isoformat(),
    }


@router.get("/{symbol}/latest")
async def get_deep_dive_latest(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = await get_latest_deep_dive(symbol, current_user.id, db)
    if not analysis:
        raise HTTPException(status_code=404, detail="No deep dive analysis found")
    return _serialize(analysis)


@router.post("/{symbol}", status_code=202)
async def trigger_deep_dive(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == current_user.id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    job_id = None
    try:
        from arq.connections import RedisSettings, create_pool
        from app.core.config import settings
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_run_deep_dive", symbol.upper(), str(current_user.id))
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        pass

    logger.info("deep_dive triggered symbol=%s user=%s job_id=%s", symbol, current_user.id, job_id)
    return {"symbol": symbol.upper(), "job_id": job_id}
```

- [ ] **Step 6: Create worker job**

```python
# backend/worker/jobs/run_deep_dive.py
import uuid
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.logging import get_logger

logger = get_logger(__name__)


async def job_run_deep_dive(ctx: dict, symbol: str, user_id: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        try:
            from app.services.deep_dive_analysis import run_deep_dive
            analysis = await run_deep_dive(symbol, uuid.UUID(user_id), db)
            await db.commit()
            logger.info("job_run_deep_dive done: symbol=%s analysis_id=%s", symbol, analysis.id)
            return {"status": "done", "analysis_id": str(analysis.id)}
        except Exception as e:
            logger.exception("job_run_deep_dive failed: symbol=%s error=%s", symbol, e)
            return {"status": "error", "error": str(e)}
```

- [ ] **Step 7: Run tests — confirm passes**

```bash
cd backend && python -m pytest tests/test_deep_dive.py -v
```

Expected: `2 passed`

---

## Task 4: Bear Case backend (model + service + API + worker job)

**Files:**
- Create: `backend/app/models/bear_case_analysis.py`
- Create: `backend/app/services/bear_case_analysis.py`
- Create: `backend/app/api/bear_case_analysis.py`
- Create: `backend/worker/jobs/run_bear_case.py`
- Create: `backend/tests/test_bear_case.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_bear_case.py
import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

VALID_RESPONSE = json.dumps({
    "red_flags": [
        {
            "rank": 1,
            "title": "Gross margin compression",
            "severity": "high",
            "data_source": "yfinance",
            "evidence": "Gross margin fell from 52% to 47% over last 4 quarters.",
            "detail": "Sustained compression signals pricing pressure from NVDA.",
        },
        {
            "rank": 2,
            "title": "Customer concentration risk",
            "severity": "medium",
            "data_source": "llm_knowledge",
            "evidence": "Top hyperscaler customers account for ~30% of AI GPU revenue.",
            "detail": "Single hyperscaler capex cuts could meaningfully impact revenue.",
        },
        {
            "rank": 3,
            "title": "Elevated short interest",
            "severity": "low",
            "data_source": "yfinance",
            "evidence": "Short interest at 4.2% of float.",
            "detail": "Market skepticism around near-term execution.",
        },
    ],
    "summary": "Margin pressure and customer concentration are the two most credible bear theses.",
})


@pytest.mark.asyncio
async def test_run_bear_case_saves_analysis():
    from app.services.bear_case_analysis import run_bear_case
    from app.services.llm_gateway import LLMGatewayResult

    mock_db = AsyncMock()
    mock_asset = MagicMock()
    mock_asset.id = uuid.uuid4()
    mock_asset.name = "Advanced Micro Devices"
    mock_asset.symbol = "AMD"
    mock_asset.metadata_ = {"sector": "Technology"}
    mock_result_row = MagicMock()
    mock_result_row.scalar_one_or_none.return_value = mock_asset
    mock_db.execute = AsyncMock(return_value=mock_result_row)

    gateway_result = LLMGatewayResult(
        content=VALID_RESPONSE, prompt="test",
        tokens_in=150, tokens_out=300, cost_usd=0.002,
        cost_thb=0.07, exchange_rate=35.0,
        model="claude-3-5-sonnet", provider="anthropic",
    )

    mock_yf_info = {
        "grossMargins": 0.512, "operatingMargins": 0.22,
        "revenueGrowth": 0.22, "debtToEquity": 12.5,
        "shortPercentOfFloat": 0.042,
    }
    mock_qf = MagicMock()
    mock_qf.loc = {}

    with patch("app.services.bear_case_analysis.LLMGateway") as MockGateway, \
         patch("app.services.bear_case_analysis.yf") as mock_yf:
        mock_gw = AsyncMock()
        mock_gw.complete = AsyncMock(return_value=gateway_result)
        MockGateway.return_value = mock_gw

        mock_ticker = MagicMock()
        mock_ticker.info = mock_yf_info
        mock_ticker.quarterly_financials = mock_qf
        mock_yf.Ticker.return_value = mock_ticker

        analysis = await run_bear_case("AMD", uuid.uuid4(), mock_db)

    assert len(analysis.red_flags) == 3
    assert analysis.red_flags[0]["rank"] == 1
    assert analysis.red_flags[0]["severity"] == "high"
    assert analysis.summary != ""
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_run_bear_case_raises_if_asset_not_found():
    from app.services.bear_case_analysis import run_bear_case

    mock_db = AsyncMock()
    mock_result_row = MagicMock()
    mock_result_row.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result_row)

    with pytest.raises(ValueError, match="not found"):
        await run_bear_case("FAKE", uuid.uuid4(), mock_db)
```

- [ ] **Step 2: Run test — confirm fails**

```bash
cd backend && python -m pytest tests/test_bear_case.py -v 2>&1 | head -10
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Create model**

```python
# backend/app/models/bear_case_analysis.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BearCaseAnalysis(Base):
    __tablename__ = "bear_case_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)

    red_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 4: Create service**

```python
# backend/app/services/bear_case_analysis.py
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import yfinance as yf
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.bear_case_analysis import BearCaseAnalysis
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


def _fetch_yfinance_vars(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        gross_margin = info.get("grossMargins", 0)
        op_margin = info.get("operatingMargins", 0)
        rev_growth = info.get("revenueGrowth", 0)
        debt_equity = info.get("debtToEquity", 0) or 0
        short_pct = info.get("shortPercentOfFloat", 0) or 0

        # Last 4 quarters gross margins from quarterly financials
        try:
            qf = ticker.quarterly_financials
            gp_row = qf.loc["Gross Profit"] if "Gross Profit" in qf.index else None
            rev_row = qf.loc["Total Revenue"] if "Total Revenue" in qf.index else None
            if gp_row is not None and rev_row is not None:
                q_margins = [
                    f"{float(gp / rv) * 100:.1f}%" if rv else "N/A"
                    for gp, rv in zip(gp_row.iloc[:4], rev_row.iloc[:4])
                ]
                gross_margins_4q = ", ".join(q_margins)
            else:
                gross_margins_4q = f"{gross_margin * 100:.1f}% (TTM only)"
        except Exception:
            gross_margins_4q = f"{gross_margin * 100:.1f}% (TTM only)"

        return {
            "gross_margins_4q": gross_margins_4q,
            "revenue_growth_yoy": f"{rev_growth * 100:.1f}",
            "operating_margin": f"{op_margin * 100:.1f}",
            "debt_equity": f"{debt_equity:.1f}",
            "short_interest_pct": f"{short_pct * 100:.1f}",
        }
    except Exception as e:
        logger.warning("yfinance fetch failed for %s: %s — using N/A defaults", symbol, e)
        return {
            "gross_margins_4q": "N/A",
            "revenue_growth_yoy": "N/A",
            "operating_margin": "N/A",
            "debt_equity": "N/A",
            "short_interest_pct": "N/A",
        }


async def run_bear_case(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> BearCaseAnalysis:
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise ValueError(f"Asset {symbol} not found for user")

    yf_vars = _fetch_yfinance_vars(symbol.upper())

    variables = {
        "symbol": symbol.upper(),
        "company_name": asset.name,
        "sector": asset.metadata_.get("sector", "Unknown"),
        **yf_vars,
    }

    gateway = LLMGateway(db)
    result = await gateway.complete("bear_case", user_id, variables)

    parsed = _parse_json(result.content)
    if not parsed:
        raise ValueError(f"LLM returned invalid JSON: {result.content[:200]}")

    analysis = BearCaseAnalysis(
        id=uuid.uuid4(),
        user_id=user_id,
        asset_id=asset.id,
        red_flags=parsed.get("red_flags", []),
        summary=parsed.get("summary", ""),
        provider=result.provider,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=Decimal(str(result.cost_usd)),
    )
    db.add(analysis)
    await db.flush()
    logger.info("BearCaseAnalysis saved: user=%s symbol=%s", user_id, symbol)
    return analysis


async def get_latest_bear_case(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> BearCaseAnalysis | None:
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        return None
    result = await db.execute(
        select(BearCaseAnalysis)
        .where(BearCaseAnalysis.asset_id == asset.id, BearCaseAnalysis.user_id == user_id)
        .order_by(desc(BearCaseAnalysis.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 5: Create API router**

```python
# backend/app/api/bear_case_analysis.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.user import User
from app.services.bear_case_analysis import get_latest_bear_case

router = APIRouter(prefix="/analysis/bear-case", tags=["bear-case"])
logger = get_logger(__name__)


def _serialize(a) -> dict:
    return {
        "id": str(a.id),
        "asset_id": str(a.asset_id) if a.asset_id else None,
        "red_flags": a.red_flags,
        "summary": a.summary,
        "provider": a.provider,
        "model": a.model,
        "tokens_in": a.tokens_in,
        "tokens_out": a.tokens_out,
        "cost_usd": float(a.cost_usd),
        "created_at": a.created_at.isoformat(),
    }


@router.get("/{symbol}/latest")
async def get_bear_case_latest(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = await get_latest_bear_case(symbol, current_user.id, db)
    if not analysis:
        raise HTTPException(status_code=404, detail="No bear case analysis found")
    return _serialize(analysis)


@router.post("/{symbol}", status_code=202)
async def trigger_bear_case(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == current_user.id)
    )
    if not asset_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    job_id = None
    try:
        from arq.connections import RedisSettings, create_pool
        from app.core.config import settings
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_run_bear_case", symbol.upper(), str(current_user.id))
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        pass

    logger.info("bear_case triggered symbol=%s user=%s job_id=%s", symbol, current_user.id, job_id)
    return {"symbol": symbol.upper(), "job_id": job_id}
```

- [ ] **Step 6: Create worker job**

```python
# backend/worker/jobs/run_bear_case.py
import uuid
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.logging import get_logger

logger = get_logger(__name__)


async def job_run_bear_case(ctx: dict, symbol: str, user_id: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        try:
            from app.services.bear_case_analysis import run_bear_case
            analysis = await run_bear_case(symbol, uuid.UUID(user_id), db)
            await db.commit()
            logger.info("job_run_bear_case done: symbol=%s analysis_id=%s", symbol, analysis.id)
            return {"status": "done", "analysis_id": str(analysis.id)}
        except Exception as e:
            logger.exception("job_run_bear_case failed: symbol=%s error=%s", symbol, e)
            return {"status": "error", "error": str(e)}
```

- [ ] **Step 7: Run tests — confirm passes**

```bash
cd backend && python -m pytest tests/test_bear_case.py -v
```

Expected: `2 passed`

---

## Task 5: Peer Comparison backend (model + service + API + worker job)

**Files:**
- Create: `backend/app/models/peer_comparison_analysis.py`
- Create: `backend/app/services/peer_comparison_analysis.py`
- Create: `backend/app/api/peer_comparison_analysis.py`
- Create: `backend/worker/jobs/run_peer_comparison.py`
- Create: `backend/tests/test_peer_comparison.py`

Note: peer comparison uses TWO LLM calls (peer discovery sub-call + main analysis). The sub-call uses the same `peer_comparison` FeatureLLMConfig but calls the adapter directly, logs to `LLMCallLog` manually, then the main call uses `LLMGateway.complete()` normally.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_peer_comparison.py
import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PEER_DISCOVERY_RESPONSE = json.dumps(["NVDA", "INTC", "QCOM"])

MAIN_ANALYSIS_RESPONSE = json.dumps({
    "sector_label": "AI Compute / CPU",
    "methodology_note": "Value/Growth Score = P/S TTM / YoY Revenue Growth %",
    "ranked": [
        {
            "ticker": "AMD", "company_name": "Advanced Micro Devices",
            "ps_ttm": 8.1, "ps_forward": 7.4, "ev_ebitda": 34.0,
            "gross_margin_pct": 51.2, "yoy_revenue_growth_pct": 22.0,
            "revenue_trend": "Reaccelerating", "value_growth_score": 0.37,
            "label": "BEST", "notes": "Best value/growth ratio in sector.",
        },
        {
            "ticker": "NVDA", "company_name": "NVIDIA Corp",
            "ps_ttm": 27.2, "ps_forward": 19.8, "ev_ebitda": 44.0,
            "gross_margin_pct": 74.1, "yoy_revenue_growth_pct": 64.0,
            "revenue_trend": "Decelerating", "value_growth_score": 0.42,
            "label": "FAIR", "notes": "Premium valuation justified by AI dominance.",
        },
        {
            "ticker": "INTC", "company_name": "Intel Corp",
            "ps_ttm": 1.9, "ps_forward": 1.8, "ev_ebitda": None,
            "gross_margin_pct": 37.4, "yoy_revenue_growth_pct": 3.0,
            "revenue_trend": "Stagnant", "value_growth_score": 0.63,
            "label": "AVOID", "notes": "Low growth despite cheap valuation.",
        },
    ],
})


@pytest.mark.asyncio
async def test_run_peer_comparison_saves_analysis():
    from app.services.peer_comparison_analysis import run_peer_comparison
    from app.services.llm_gateway import LLMGatewayResult

    mock_db = AsyncMock()
    mock_asset = MagicMock()
    mock_asset.id = uuid.uuid4()
    mock_asset.name = "Advanced Micro Devices"
    mock_asset.symbol = "AMD"
    mock_asset.metadata_ = {"sector": "Technology"}
    mock_result_row = MagicMock()
    mock_result_row.scalar_one_or_none.return_value = mock_asset
    mock_db.execute = AsyncMock(return_value=mock_result_row)

    discovery_result = LLMGatewayResult(
        content=PEER_DISCOVERY_RESPONSE, prompt="test",
        tokens_in=50, tokens_out=20, cost_usd=0.0001,
        cost_thb=0.003, exchange_rate=35.0,
        model="claude-3-5-sonnet", provider="anthropic",
    )
    main_result = LLMGatewayResult(
        content=MAIN_ANALYSIS_RESPONSE, prompt="test",
        tokens_in=200, tokens_out=400, cost_usd=0.003,
        cost_thb=0.1, exchange_rate=35.0,
        model="claude-3-5-sonnet", provider="anthropic",
    )

    mock_yf_data = {
        "AMD": {"ps_ttm": 8.1, "ps_forward": 7.4, "ev_ebitda": 34.0, "gross_margin_pct": 51.2, "yoy_revenue_growth_pct": 22.0},
        "NVDA": {"ps_ttm": 27.2, "ps_forward": 19.8, "ev_ebitda": 44.0, "gross_margin_pct": 74.1, "yoy_revenue_growth_pct": 64.0},
        "INTC": {"ps_ttm": 1.9, "ps_forward": 1.8, "ev_ebitda": None, "gross_margin_pct": 37.4, "yoy_revenue_growth_pct": 3.0},
        "QCOM": {"ps_ttm": 4.5, "ps_forward": 4.0, "ev_ebitda": 12.0, "gross_margin_pct": 55.0, "yoy_revenue_growth_pct": 9.0},
    }

    with patch("app.services.peer_comparison_analysis.LLMGateway") as MockGateway, \
         patch("app.services.peer_comparison_analysis._fetch_yfinance_metrics") as mock_yf, \
         patch("app.services.peer_comparison_analysis._discover_peers") as mock_discover:
        mock_gw = AsyncMock()
        mock_gw.complete = AsyncMock(return_value=main_result)
        MockGateway.return_value = mock_gw

        mock_discover.return_value = (["NVDA", "INTC", "QCOM"], discovery_result)
        mock_yf.return_value = mock_yf_data

        analysis = await run_peer_comparison("AMD", uuid.uuid4(), mock_db)

    assert analysis.sector_label == "AI Compute / CPU"
    assert len(analysis.ranked) == 3
    assert analysis.ranked[0]["label"] == "BEST"
    mock_db.add.assert_called_once()
```

- [ ] **Step 2: Run test — confirm fails**

```bash
cd backend && python -m pytest tests/test_peer_comparison.py -v 2>&1 | head -10
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Create model**

```python
# backend/app/models/peer_comparison_analysis.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PeerComparisonAnalysis(Base):
    __tablename__ = "peer_comparison_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)

    sector_label: Mapped[str] = mapped_column(String(100), nullable=False)
    ranked: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    methodology_note: Mapped[str] = mapped_column(Text, nullable=False)

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 4: Create service**

```python
# backend/app/services/peer_comparison_analysis.py
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import yfinance as yf
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.llm_call_log import LLMCallLog
from app.models.peer_comparison_analysis import PeerComparisonAnalysis
from app.services.exchange_rate import get_current_usd_thb
from app.services.llm_gateway import LLMGateway, LLMGatewayResult

logger = get_logger(__name__)

PEER_DISCOVERY_SYSTEM = (
    "You are a market analyst. Given a stock ticker and sector, list the 3-5 most direct competitors. "
    "Respond ONLY with a JSON array of uppercase ticker symbols. Example: [\"NVDA\", \"INTC\", \"QCOM\"]"
)


def _parse_json(content: str) -> dict | list | None:
    try:
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except (json.JSONDecodeError, IndexError):
        return None


def _fetch_yfinance_metrics(tickers: list[str]) -> dict[str, dict]:
    result = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            result[t] = {
                "ps_ttm": info.get("priceToSalesTrailing12Months"),
                "ps_forward": info.get("forwardPE"),  # approximation
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "gross_margin_pct": round((info.get("grossMargins") or 0) * 100, 1),
                "yoy_revenue_growth_pct": round((info.get("revenueGrowth") or 0) * 100, 1),
            }
        except Exception as e:
            logger.warning("yfinance failed for %s: %s", t, e)
            result[t] = {
                "ps_ttm": None, "ps_forward": None, "ev_ebitda": None,
                "gross_margin_pct": None, "yoy_revenue_growth_pct": None,
            }
    return result


async def _discover_peers(
    symbol: str,
    sector: str,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[list[str], LLMGatewayResult]:
    """First LLM call: identify peer tickers. Uses same peer_comparison config but hardcoded prompt."""
    from app.models.feature_llm_config import FeatureLLMConfig
    from app.models.provider_config import ProviderConfig
    from app.core.encryption import decrypt
    from app.services.llm_service import calc_cost
    from app.services.llm_gateway import _build_adapter

    config_result = await db.execute(
        select(FeatureLLMConfig).where(
            FeatureLLMConfig.feature_key == "peer_comparison",
            FeatureLLMConfig.user_id == user_id,
        )
    )
    config = config_result.scalar_one_or_none()
    if not config:
        raise ValueError("No LLM config for 'peer_comparison'. Configure it in Settings → AI.")

    provider_result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.id == config.provider_config_id)
    )
    provider = provider_result.scalar_one_or_none()
    if not provider or not provider.is_connected:
        raise ValueError("peer_comparison provider not connected")

    api_key = decrypt(provider.encrypted_api_key) if provider.encrypted_api_key else None
    adapter = _build_adapter(provider.provider, api_key, getattr(provider, "host_url", None))

    human = f"Ticker: {symbol}\nSector: {sector}\nList 3-5 direct competitors as a JSON array of tickers."
    response = await adapter.complete(PEER_DISCOVERY_SYSTEM, human, config.model)

    usd_thb = await get_current_usd_thb(db)
    cost_thb = float(response.cost_usd) * float(usd_thb) if usd_thb else 0.0

    log = LLMCallLog(
        user_id=user_id,
        feature_key="peer_comparison",
        provider=provider.provider,
        model=config.model,
        prompt_in=f"SYSTEM: {PEER_DISCOVERY_SYSTEM}\n\nHUMAN: {human}",
        response_out=response.content,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        cost_usd=response.cost_usd,
        cost_thb=cost_thb,
        exchange_rate=float(usd_thb) if usd_thb else 0.0,
    )
    db.add(log)
    await db.flush()

    peers = _parse_json(response.content)
    if not isinstance(peers, list):
        logger.warning("Peer discovery returned non-list: %s — using defaults", response.content[:100])
        peers = []

    gateway_result = LLMGatewayResult(
        content=response.content, prompt=human,
        tokens_in=response.tokens_in, tokens_out=response.tokens_out,
        cost_usd=float(response.cost_usd), cost_thb=cost_thb,
        exchange_rate=float(usd_thb) if usd_thb else 0.0,
        model=config.model, provider=provider.provider,
    )
    return [t.upper() for t in peers[:5]], gateway_result


def _build_financial_table(symbol: str, metrics: dict[str, dict]) -> str:
    rows = [f"{'Ticker':<8} {'P/S TTM':>10} {'EV/EBITDA':>12} {'Gross Margin':>14} {'Rev Growth YoY':>16}"]
    rows.append("-" * 65)
    all_tickers = [symbol] + [t for t in metrics if t != symbol]
    for t in all_tickers:
        m = metrics.get(t, {})
        rows.append(
            f"{t:<8} "
            f"{str(m.get('ps_ttm') or 'N/A'):>10} "
            f"{str(m.get('ev_ebitda') or 'N/A'):>12} "
            f"{str(m.get('gross_margin_pct') or 'N/A') + '%':>14} "
            f"{str(m.get('yoy_revenue_growth_pct') or 'N/A') + '%':>16}"
        )
    return "\n".join(rows)


async def run_peer_comparison(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> PeerComparisonAnalysis:
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise ValueError(f"Asset {symbol} not found for user")

    sector = asset.metadata_.get("sector", "Unknown")

    peers, _ = await _discover_peers(symbol.upper(), sector, user_id, db)
    all_tickers = [symbol.upper()] + peers
    metrics = _fetch_yfinance_metrics(all_tickers)
    financial_table = _build_financial_table(symbol.upper(), metrics)

    variables = {
        "symbol": symbol.upper(),
        "sector": sector,
        "financial_table": financial_table,
    }

    gateway = LLMGateway(db)
    result = await gateway.complete("peer_comparison", user_id, variables)

    parsed = _parse_json(result.content)
    if not parsed or not isinstance(parsed, dict):
        raise ValueError(f"LLM returned invalid JSON: {result.content[:200]}")

    analysis = PeerComparisonAnalysis(
        id=uuid.uuid4(),
        user_id=user_id,
        asset_id=asset.id,
        sector_label=parsed.get("sector_label", sector),
        ranked=parsed.get("ranked", []),
        methodology_note=parsed.get("methodology_note", "Value/Growth Score = P/S TTM / YoY Revenue Growth %"),
        provider=result.provider,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=Decimal(str(result.cost_usd)),
    )
    db.add(analysis)
    await db.flush()
    logger.info("PeerComparisonAnalysis saved: user=%s symbol=%s peers=%s", user_id, symbol, peers)
    return analysis


async def get_latest_peer_comparison(
    symbol: str, user_id: uuid.UUID, db: AsyncSession
) -> PeerComparisonAnalysis | None:
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        return None
    result = await db.execute(
        select(PeerComparisonAnalysis)
        .where(PeerComparisonAnalysis.asset_id == asset.id, PeerComparisonAnalysis.user_id == user_id)
        .order_by(desc(PeerComparisonAnalysis.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 5: Create API router**

```python
# backend/app/api/peer_comparison_analysis.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.user import User
from app.services.peer_comparison_analysis import get_latest_peer_comparison

router = APIRouter(prefix="/analysis/peer-comparison", tags=["peer-comparison"])
logger = get_logger(__name__)


def _serialize(a) -> dict:
    return {
        "id": str(a.id),
        "asset_id": str(a.asset_id) if a.asset_id else None,
        "sector_label": a.sector_label,
        "ranked": a.ranked,
        "methodology_note": a.methodology_note,
        "provider": a.provider,
        "model": a.model,
        "tokens_in": a.tokens_in,
        "tokens_out": a.tokens_out,
        "cost_usd": float(a.cost_usd),
        "created_at": a.created_at.isoformat(),
    }


@router.get("/{symbol}/latest")
async def get_peer_comparison_latest(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = await get_latest_peer_comparison(symbol, current_user.id, db)
    if not analysis:
        raise HTTPException(status_code=404, detail="No peer comparison found")
    return _serialize(analysis)


@router.post("/{symbol}", status_code=202)
async def trigger_peer_comparison(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == current_user.id)
    )
    if not asset_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    job_id = None
    try:
        from arq.connections import RedisSettings, create_pool
        from app.core.config import settings
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_run_peer_comparison", symbol.upper(), str(current_user.id))
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        pass

    logger.info("peer_comparison triggered symbol=%s user=%s job_id=%s", symbol, current_user.id, job_id)
    return {"symbol": symbol.upper(), "job_id": job_id}
```

- [ ] **Step 6: Create worker job**

```python
# backend/worker/jobs/run_peer_comparison.py
import uuid
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.logging import get_logger

logger = get_logger(__name__)


async def job_run_peer_comparison(ctx: dict, symbol: str, user_id: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        try:
            from app.services.peer_comparison_analysis import run_peer_comparison
            analysis = await run_peer_comparison(symbol, uuid.UUID(user_id), db)
            await db.commit()
            logger.info("job_run_peer_comparison done: symbol=%s analysis_id=%s", symbol, analysis.id)
            return {"status": "done", "analysis_id": str(analysis.id)}
        except Exception as e:
            logger.exception("job_run_peer_comparison failed: symbol=%s error=%s", symbol, e)
            return {"status": "error", "error": str(e)}
```

- [ ] **Step 7: Run tests — confirm passes**

```bash
cd backend && python -m pytest tests/test_peer_comparison.py -v
```

Expected: `1 passed`

---

## Task 6: Combined Verdict backend (model + service + API + worker job)

**Files:**
- Create: `backend/app/models/combined_verdict.py`
- Create: `backend/app/services/combined_verdict.py`
- Create: `backend/app/api/combined_verdict.py`
- Create: `backend/worker/jobs/run_combined_verdict.py`
- Create: `backend/tests/test_combined_verdict.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_combined_verdict.py
import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

VALID_RESPONSE = json.dumps({
    "verdict": "buy",
    "conviction": 7,
    "bull_thesis": "AMD is gaining AI GPU share with MI300X at a cheaper valuation than NVDA.",
    "bear_thesis": "Execution risk on next-gen GPU roadmap and NVDA's ecosystem lock-in.",
    "key_risks": ["Customer concentration", "GPU supply chain constraints"],
    "reasoning": "Peer comparison shows best value/growth score. Bear case risks are manageable.",
    "based_on": ["top_down_analysis", "deep_dive", "peer_comparison", "bear_case"],
})


@pytest.mark.asyncio
async def test_run_combined_verdict_saves_result():
    from app.services.combined_verdict import run_combined_verdict
    from app.services.llm_gateway import LLMGatewayResult

    mock_db = AsyncMock()
    mock_asset = MagicMock()
    mock_asset.id = uuid.uuid4()
    mock_asset.name = "Advanced Micro Devices"
    mock_asset.symbol = "AMD"

    mock_top_down = MagicMock()
    mock_top_down.verdict = "BUY"
    mock_top_down.mega_trend = "AI compute buildout."
    mock_top_down.financial_health = "Strong balance sheet."

    mock_deep_dive = MagicMock()
    mock_deep_dive.business_model = "CPU/GPU chip designer."
    mock_deep_dive.moat_edge_type = "switching_cost"
    mock_deep_dive.asymmetry_verdict = "yes"

    mock_peer = MagicMock()
    mock_peer.sector_label = "AI Compute / CPU"
    mock_peer.ranked = [{"ticker": "AMD", "label": "BEST", "value_growth_score": 0.37}]

    mock_bear = MagicMock()
    mock_bear.red_flags = [{"rank": 1, "title": "Margin compression", "severity": "medium"}]
    mock_bear.summary = "Manageable risks."

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        row = MagicMock()
        if call_count == 1:
            row.scalar_one_or_none.return_value = mock_asset
        elif call_count == 2:
            row.scalar_one_or_none.return_value = mock_top_down
        elif call_count == 3:
            row.scalar_one_or_none.return_value = mock_deep_dive
        elif call_count == 4:
            row.scalar_one_or_none.return_value = mock_peer
        elif call_count == 5:
            row.scalar_one_or_none.return_value = mock_bear
        return row

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    gateway_result = LLMGatewayResult(
        content=VALID_RESPONSE, prompt="test",
        tokens_in=500, tokens_out=300, cost_usd=0.005,
        cost_thb=0.175, exchange_rate=35.0,
        model="claude-3-5-sonnet", provider="anthropic",
    )

    with patch("app.services.combined_verdict.LLMGateway") as MockGateway:
        mock_gw = AsyncMock()
        mock_gw.complete = AsyncMock(return_value=gateway_result)
        MockGateway.return_value = mock_gw

        verdict = await run_combined_verdict("AMD", uuid.uuid4(), mock_db)

    assert verdict.verdict == "buy"
    assert verdict.conviction == 7
    assert "top_down_analysis" in verdict.based_on
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_run_combined_verdict_raises_if_no_analyses():
    from app.services.combined_verdict import run_combined_verdict

    mock_db = AsyncMock()
    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        row = MagicMock()
        row.scalar_one_or_none.return_value = None
        return row

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    with pytest.raises(ValueError, match="no analyses available"):
        await run_combined_verdict("AMD", uuid.uuid4(), mock_db)
```

- [ ] **Step 2: Run test — confirm fails**

```bash
cd backend && python -m pytest tests/test_combined_verdict.py -v 2>&1 | head -10
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Create model**

```python
# backend/app/models/combined_verdict.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CombinedVerdict(Base):
    __tablename__ = "combined_verdicts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)

    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    conviction: Mapped[int] = mapped_column(Integer, nullable=False)
    bull_thesis: Mapped[str] = mapped_column(Text, nullable=False)
    bear_thesis: Mapped[str] = mapped_column(Text, nullable=False)
    key_risks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    based_on: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 4: Create service**

```python
# backend/app/services/combined_verdict.py
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

    # Fetch latest of each analysis (all optional except: need at least 1)
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
```

- [ ] **Step 5: Create API router**

```python
# backend/app/api/combined_verdict.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.user import User
from app.services.combined_verdict import get_latest_combined_verdict

router = APIRouter(prefix="/analysis/combined-verdict", tags=["combined-verdict"])
logger = get_logger(__name__)


def _serialize(v) -> dict:
    return {
        "id": str(v.id),
        "asset_id": str(v.asset_id) if v.asset_id else None,
        "verdict": v.verdict,
        "conviction": v.conviction,
        "bull_thesis": v.bull_thesis,
        "bear_thesis": v.bear_thesis,
        "key_risks": v.key_risks,
        "reasoning": v.reasoning,
        "based_on": v.based_on,
        "provider": v.provider,
        "model": v.model,
        "tokens_in": v.tokens_in,
        "tokens_out": v.tokens_out,
        "cost_usd": float(v.cost_usd),
        "created_at": v.created_at.isoformat(),
    }


@router.get("/{symbol}/latest")
async def get_combined_verdict_latest(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verdict = await get_latest_combined_verdict(symbol, current_user.id, db)
    if not verdict:
        raise HTTPException(status_code=404, detail="No combined verdict found")
    return _serialize(verdict)


@router.post("/{symbol}", status_code=202)
async def trigger_combined_verdict(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset_result = await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == current_user.id)
    )
    if not asset_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    job_id = None
    try:
        from arq.connections import RedisSettings, create_pool
        from app.core.config import settings
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_run_combined_verdict", symbol.upper(), str(current_user.id))
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        pass

    logger.info("combined_verdict triggered symbol=%s user=%s job_id=%s", symbol, current_user.id, job_id)
    return {"symbol": symbol.upper(), "job_id": job_id}
```

- [ ] **Step 6: Create worker job**

```python
# backend/worker/jobs/run_combined_verdict.py
import uuid
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.logging import get_logger

logger = get_logger(__name__)


async def job_run_combined_verdict(ctx: dict, symbol: str, user_id: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        try:
            from app.services.combined_verdict import run_combined_verdict
            verdict = await run_combined_verdict(symbol, uuid.UUID(user_id), db)
            await db.commit()
            logger.info("job_run_combined_verdict done: symbol=%s verdict=%s", symbol, verdict.verdict)
            return {"status": "done", "verdict": verdict.verdict, "conviction": verdict.conviction}
        except Exception as e:
            logger.exception("job_run_combined_verdict failed: symbol=%s error=%s", symbol, e)
            return {"status": "error", "error": str(e)}
```

- [ ] **Step 7: Run tests — confirm passes**

```bash
cd backend && python -m pytest tests/test_combined_verdict.py -v
```

Expected: `2 passed`

---

## Task 7: Register routers + worker jobs

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Register routers in `main.py`**

In `backend/app/main.py`, add imports and `include_router` calls:

```python
# Add to imports at top:
from app.api import (
    analysis, assets, auth, cash_balance, chat, dividends, documents,
    events, feature_llm_config, health, import_pipeline, ipos, llm_pricing, llm_usage,
    overview, pipeline, platforms, portfolio, provider_config, research, settings, system,
    top_down_analysis, watchlist,
    deep_dive_analysis, bear_case_analysis, peer_comparison_analysis, combined_verdict,
)
```

```python
# Add after app.include_router(top_down_analysis.router, prefix="/api/v1"):
app.include_router(deep_dive_analysis.router, prefix="/api/v1")
app.include_router(bear_case_analysis.router, prefix="/api/v1")
app.include_router(peer_comparison_analysis.router, prefix="/api/v1")
app.include_router(combined_verdict.router, prefix="/api/v1")
```

- [ ] **Step 2: Register jobs in `worker/main.py`**

In `backend/worker/main.py`, add imports and register in `functions` list:

```python
# Add to imports:
from worker.jobs.run_deep_dive import job_run_deep_dive
from worker.jobs.run_bear_case import job_run_bear_case
from worker.jobs.run_peer_comparison import job_run_peer_comparison
from worker.jobs.run_combined_verdict import job_run_combined_verdict
```

```python
# Add to WorkerSettings.functions list:
job_run_deep_dive,
job_run_bear_case,
job_run_peer_comparison,
job_run_combined_verdict,
```

- [ ] **Step 3: Verify app starts without errors**

```bash
cd backend && python -c "from app.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Verify worker imports without errors**

```bash
cd backend && python -c "from worker.main import WorkerSettings; print(len(WorkerSettings.functions), 'jobs registered')"
```

Expected: a number ≥ 23 (existing + 4 new)

- [ ] **Step 5: Run all new tests together**

```bash
cd backend && python -m pytest tests/test_deep_dive.py tests/test_bear_case.py tests/test_peer_comparison.py tests/test_combined_verdict.py -v
```

Expected: `6 passed` (2 + 2 + 1 + 2 — adjust count if you added more)

---

## Task 8: Register frontend feature labels and settings keys

**Files:**
- Modify: `frontend/lib/services/feature-llm-config.ts`
- Modify: `frontend/components/settings/AISettings.tsx`

- [ ] **Step 1: Add labels to `feature-llm-config.ts`**

In `frontend/lib/services/feature-llm-config.ts`, extend `FEATURE_LABELS`:

```typescript
export const FEATURE_LABELS: Record<string, string> = {
  import_translator: "Import Translator",
  portfolio_analysis: "Portfolio Analysis",
  overview_analysis: "Overview AI Analysis",
  chat: "Chat Assistant",
  watchlist_scan: "Watchlist Scanner",
  watchlist_discovery: "Watchlist Discovery",
  ipo_analysis: "IPO Analysis",
  top_down_analysis: "Top-Down Analysis",
  top_down_discovery: "Top-Down Discovery",
  deep_dive: "Deep Dive Analysis",
  peer_comparison: "Peer Comparison",
  bear_case: "Bear Case",
  combined_verdict: "Combined Verdict",
};
```

- [ ] **Step 2: Add keys to `AISettings.tsx`**

In `frontend/components/settings/AISettings.tsx`, extend `FEATURE_KEYS`:

```typescript
const FEATURE_KEYS = [
  "import_translator",
  "portfolio_analysis",
  "overview_analysis",
  "chat",
  "watchlist_scan",
  "watchlist_discovery",
  "ipo_analysis",
  "top_down_analysis",
  "top_down_discovery",
  "deep_dive",
  "peer_comparison",
  "bear_case",
  "combined_verdict",
];
```

- [ ] **Step 3: Verify Settings page shows all 4 new rows**

Start dev server and open Settings → AI. Confirm "Deep Dive Analysis", "Peer Comparison", "Bear Case", "Combined Verdict" appear in the feature config list.

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/settings/ai` — confirm 4 new rows visible.

---

## Completion Checklist

- [ ] All 4 feature keys in `feature_llm_config.py` FEATURE_KEYS tuple
- [ ] All 4 keys in `llm_gateway.py` FEATURE_KEYS + SYSTEM_PROMPTS + HUMAN_PROMPTS + DEFAULT_SYSTEM_PROMPTS
- [ ] All 4 keys in `feature-llm-config.ts` FEATURE_LABELS
- [ ] All 4 keys in `AISettings.tsx` FEATURE_KEYS
- [ ] Migration 041 applied successfully
- [ ] 4 new models created
- [ ] 4 new services created (deep_dive, bear_case use LLMGateway; peer_comparison has 2-step; combined_verdict reads from DB)
- [ ] 4 new API routers created (GET latest + POST trigger)
- [ ] 4 new worker jobs created
- [ ] All routers registered in `main.py`
- [ ] All jobs registered in `worker/main.py`
- [ ] All 4 settings rows visible in Settings → AI
- [ ] 6 tests passing

**Next:** `docs/superpowers/plans/2026-05-21-analysis-ai-features-part2-frontend.md`
