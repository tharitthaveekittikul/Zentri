# Overview AI Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-triggered AI Portfolio Analysis section to the Overview page, backed by a new `overview_analysis` feature key, stored result model, and POST/GET API endpoints.

**Architecture:** New `OverviewAnalysis` DB model stores structured JSON results. `POST /overview/ai-analysis` fetches portfolio context, calls LLMGateway, parses + stores result. `GET /overview/ai-analysis/latest` returns last stored result. Frontend renders an `AIAnalysisCard` with score, grade, insights, and top action. Re-analysis guard returns `requires_confirmation: true` if last run < 30 min ago; second call with `?force=true` bypasses guard. Confirmation dialog (Plan 5) wires into the trigger button.

**Dependencies:** Plan 1 (Gateway + Prompts) must be complete — `overview_analysis` prompts are defined there.

**Tech Stack:** Python, SQLAlchemy async, Alembic, FastAPI, Next.js, TypeScript

---

## File Map

| File | Change |
|---|---|
| `backend/app/models/overview_analysis.py` | NEW: OverviewAnalysis SQLAlchemy model |
| `backend/app/models/__init__.py` | Register new model |
| `backend/alembic/versions/<timestamp>_add_overview_analysis.py` | NEW: migration |
| `backend/app/models/feature_llm_config.py` | Add `overview_analysis` to FEATURE_KEYS |
| `backend/app/schemas/overview.py` | Add OverviewAnalysisOut schema |
| `backend/app/services/overview_analysis.py` | NEW: build variables + call gateway |
| `backend/app/api/overview.py` | Add POST + GET endpoints |
| `backend/tests/test_overview_analysis.py` | NEW: service + API tests |
| `frontend/components/overview/AIAnalysisCard.tsx` | NEW: display component |
| `frontend/app/(auth)/overview/page.tsx` | Add AIAnalysisCard section |
| `frontend/lib/api/overviewAnalysis.ts` | NEW: API client functions |

---

### Task 1: Create OverviewAnalysis Model

**Files:**
- Create: `backend/app/models/overview_analysis.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write failing test for model import**

Create `backend/tests/test_overview_analysis.py`:

```python
import pytest

def test_overview_analysis_model_importable():
    from app.models.overview_analysis import OverviewAnalysis
    assert OverviewAnalysis.__tablename__ == "overview_analyses"

def test_overview_analysis_has_required_fields():
    from app.models.overview_analysis import OverviewAnalysis
    cols = {c.key for c in OverviewAnalysis.__table__.columns}
    assert "score" in cols
    assert "grade" in cols
    assert "portfolio_adherence_pct" in cols
    assert "insights" in cols
    assert "top_action" in cols
    assert "cost_usd" in cols
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && uv run pytest tests/test_overview_analysis.py::test_overview_analysis_model_importable -v
```
Expected: `FAILED` — module not found.

- [ ] **Step 3: Create the model**

Create `backend/app/models/overview_analysis.py`:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OverviewAnalysis(Base):
    __tablename__ = "overview_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[str] = mapped_column(String(1), nullable=False)
    portfolio_adherence_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    health: Mapped[str] = mapped_column(String(10), nullable=False)
    insights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    top_action: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    cost_thb: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 4: Register in `backend/app/models/__init__.py`**

Add to the imports:

```python
from app.models.overview_analysis import OverviewAnalysis  # noqa: F401
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_overview_analysis.py::test_overview_analysis_model_importable tests/test_overview_analysis.py::test_overview_analysis_has_required_fields -v
```
Expected: `PASSED`.

---

### Task 2: Create Alembic Migration

**Files:**
- Create: `backend/alembic/versions/<timestamp>_add_overview_analysis.py`

- [ ] **Step 1: Generate migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add_overview_analysis"
```

- [ ] **Step 2: Review generated file**

Open the generated file in `backend/alembic/versions/`. Verify it creates `overview_analyses` table with all columns. The JSONB column should appear as:
```python
sa.Column('insights', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
```

- [ ] **Step 3: Apply migration**

```bash
cd backend && uv run alembic upgrade head
```
Expected: no errors, table created.

---

### Task 3: Add `overview_analysis` to FEATURE_KEYS

**Files:**
- Modify: `backend/app/models/feature_llm_config.py`

- [ ] **Step 1: Write failing test**

```python
def test_overview_analysis_in_feature_keys():
    from app.models.feature_llm_config import FEATURE_KEYS
    assert "overview_analysis" in FEATURE_KEYS
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && uv run pytest tests/test_overview_analysis.py::test_overview_analysis_in_feature_keys -v
```

- [ ] **Step 3: Add to FEATURE_KEYS**

In `backend/app/models/feature_llm_config.py`, update:

```python
FEATURE_KEYS = (
    "import_translator",
    "portfolio_analysis",
    "chat",
    "watchlist_scan",
    "watchlist_discovery",
    "ipo_analysis",
    "overview_analysis",
)
```

- [ ] **Step 4: Run test**

```bash
cd backend && uv run pytest tests/test_overview_analysis.py::test_overview_analysis_in_feature_keys -v
```
Expected: `PASSED`.

---

### Task 4: Create Overview Analysis Service

**Files:**
- Create: `backend/app/services/overview_analysis.py`
- Test: `backend/tests/test_overview_analysis.py`

- [ ] **Step 1: Write failing tests**

```python
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.services.overview_analysis import run_overview_analysis, get_latest_overview_analysis

@pytest.mark.asyncio
async def test_run_overview_analysis_returns_stored_result(db_session, user_factory):
    user = await user_factory()
    mock_result = MagicMock()
    mock_result.content = json.dumps({
        "score": 75, "grade": "B", "portfolio_adherence_pct": 70,
        "health": "GOOD",
        "insights": [{"type": "warning", "title": "Too much tech", "message": "Reduce tech exposure."}],
        "top_action": "Rebalance into bonds."
    })
    mock_result.tokens_in = 100
    mock_result.tokens_out = 50
    mock_result.cost_usd = 0.001
    mock_result.cost_thb = 0.035
    mock_result.provider = "anthropic"
    mock_result.model = "claude-sonnet-4-6"

    with patch("app.services.overview_analysis.LLMGateway") as MockGW:
        MockGW.return_value.complete = AsyncMock(return_value=mock_result)
        result = await run_overview_analysis(db_session, user)

    assert result.score == 75
    assert result.grade == "B"
    assert len(result.insights) == 1

@pytest.mark.asyncio
async def test_get_latest_returns_none_when_no_analysis(db_session, user_factory):
    user = await user_factory()
    result = await get_latest_overview_analysis(db_session, user.id)
    assert result is None
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && uv run pytest tests/test_overview_analysis.py::test_run_overview_analysis_returns_stored_result -v
```
Expected: `FAILED` — module not found.

- [ ] **Step 3: Create the service**

Create `backend/app/services/overview_analysis.py`:

```python
from __future__ import annotations

import json
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.overview_analysis import OverviewAnalysis
from app.models.user import User
from app.services.llm_gateway import LLMGateway
from app.services import overview as overview_svc

logger = get_logger(__name__)


async def _build_variables(db: AsyncSession, user: User) -> dict:
    summary = await overview_svc.get_summary(db, user.id, user.currency_primary)
    allocation = await overview_svc.get_allocation(db, user.id, user.currency_primary)
    performance = await overview_svc.get_performance(db, user.id, "1M")

    holdings_rows = []
    for h in getattr(summary, "holdings", []):
        symbol = getattr(h, "symbol", "")
        asset_type = getattr(h, "asset_type", "")
        qty = getattr(h, "outstanding_shares", "")
        avg_cost = getattr(h, "cost_per_share", "")
        current_price = getattr(h, "current_price", "N/A")
        value = getattr(h, "current_value", "")
        alloc = getattr(h, "allocation_pct", "")
        holdings_rows.append(f"{symbol} | {asset_type} | {qty} | {avg_cost} | {current_price} | {value} | {alloc}%")

    cash_rows = []
    for c in getattr(summary, "cash_accounts", []):
        currency = getattr(c, "currency", "")
        amount = getattr(c, "balance", "")
        value = getattr(c, "value_primary", "")
        cash_rows.append(f"{currency} | {amount} | {value}")

    alloc_rows = []
    for a in allocation:
        asset_type = getattr(a, "asset_type", "")
        value = getattr(a, "value", "")
        pct = getattr(a, "percentage", "")
        alloc_rows.append(f"{asset_type} | {value} | {pct}%")

    perf_1m = getattr(performance, "change_pct", 0) or 0
    total_value = getattr(summary, "total_value", 0) or 0

    return {
        "holdings_table": "\n".join(holdings_rows) or "No holdings",
        "cash_table": "\n".join(cash_rows) or "No cash accounts",
        "allocation_table": "\n".join(alloc_rows) or "No allocation data",
        "perf_1m": f"{perf_1m:.2f}",
        "perf_3m": "N/A",
        "perf_ytd": "N/A",
        "total_value": str(total_value),
    }


async def run_overview_analysis(db: AsyncSession, user: User) -> OverviewAnalysis:
    variables = await _build_variables(db, user)
    gw = LLMGateway(db)
    result = await gw.complete("overview_analysis", user.id, variables)

    try:
        parsed = json.loads(result.content)
    except (json.JSONDecodeError, ValueError):
        logger.error("overview_analysis: failed to parse LLM JSON response")
        raise ValueError("LLM returned invalid JSON for overview_analysis")

    analysis = OverviewAnalysis(
        user_id=user.id,
        score=int(parsed.get("score", 0)),
        grade=str(parsed.get("grade", "D")),
        portfolio_adherence_pct=int(parsed.get("portfolio_adherence_pct", 0)),
        health=str(parsed.get("health", "POOR")),
        insights=parsed.get("insights", []),
        top_action=str(parsed.get("top_action", "")),
        provider=result.provider,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
        cost_thb=result.cost_thb,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    logger.info("overview_analysis stored: score=%d grade=%s user=%s", analysis.score, analysis.grade, user.id)
    return analysis


async def get_latest_overview_analysis(db: AsyncSession, user_id: uuid.UUID) -> OverviewAnalysis | None:
    result = await db.execute(
        select(OverviewAnalysis)
        .where(OverviewAnalysis.user_id == user_id)
        .order_by(desc(OverviewAnalysis.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_overview_analysis.py -v
```
Expected: `PASSED`.

---

### Task 5: Add API Endpoints

**Files:**
- Modify: `backend/app/api/overview.py`

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_post_overview_ai_analysis_returns_result(client, auth_headers):
    with patch("app.api.overview.run_overview_analysis") as mock_run:
        mock_run.return_value = MagicMock(
            id=uuid.uuid4(), score=75, grade="B",
            portfolio_adherence_pct=70, health="GOOD",
            insights=[], top_action="Rebalance.", provider="anthropic",
            model="claude-sonnet-4-6", tokens_in=100, tokens_out=50,
            cost_usd=0.001, cost_thb=0.035,
            created_at=datetime.now(timezone.utc),
        )
        resp = await client.post("/overview/ai-analysis", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["score"] == 75

@pytest.mark.asyncio
async def test_post_overview_ai_analysis_guard_returns_confirmation(client, auth_headers, existing_analysis):
    """If analysis < 30 min ago, return requires_confirmation without running LLM."""
    resp = await client.post("/overview/ai-analysis", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["requires_confirmation"] is True

@pytest.mark.asyncio
async def test_post_overview_ai_analysis_force_bypasses_guard(client, auth_headers, existing_analysis):
    with patch("app.api.overview.run_overview_analysis") as mock_run:
        mock_run.return_value = MagicMock(score=80, grade="A", ...)
        resp = await client.post("/overview/ai-analysis?force=true", headers=auth_headers)
    assert resp.status_code == 200
    assert "score" in resp.json()

@pytest.mark.asyncio
async def test_get_latest_overview_analysis_returns_none_when_empty(client, auth_headers):
    resp = await client.get("/overview/ai-analysis/latest", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() is None
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && uv run pytest tests/test_overview_analysis.py -k "api" -v
```

- [ ] **Step 3: Add endpoints to overview.py**

Add to `backend/app/api/overview.py`:

```python
from datetime import datetime, timedelta, timezone

from app.models.overview_analysis import OverviewAnalysis
from app.services.overview_analysis import get_latest_overview_analysis, run_overview_analysis


def _serialize_analysis(a: OverviewAnalysis) -> dict:
    return {
        "id": str(a.id),
        "score": a.score,
        "grade": a.grade,
        "portfolio_adherence_pct": a.portfolio_adherence_pct,
        "health": a.health,
        "insights": a.insights,
        "top_action": a.top_action,
        "provider": a.provider,
        "model": a.model,
        "tokens_in": a.tokens_in,
        "tokens_out": a.tokens_out,
        "cost_usd": float(a.cost_usd),
        "cost_thb": float(a.cost_thb),
        "created_at": a.created_at.isoformat(),
    }


@router.post("/ai-analysis")
async def trigger_overview_analysis(
    force: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    latest = await get_latest_overview_analysis(db, current_user.id)
    if latest and not force:
        age_minutes = (datetime.now(timezone.utc) - latest.created_at).total_seconds() / 60
        if age_minutes < 30:
            return {
                "requires_confirmation": True,
                "last_analyzed_minutes_ago": int(age_minutes),
            }

    analysis = await run_overview_analysis(db, current_user)
    return _serialize_analysis(analysis)


@router.get("/ai-analysis/latest")
async def get_latest_analysis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    latest = await get_latest_overview_analysis(db, current_user.id)
    if not latest:
        return None
    return _serialize_analysis(latest)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_overview_analysis.py -v
```
Expected: all `PASSED`.

---

### Task 6: Frontend — API Client + AIAnalysisCard

**Files:**
- Create: `frontend/lib/api/overviewAnalysis.ts`
- Create: `frontend/components/overview/AIAnalysisCard.tsx`

- [ ] **Step 1: Create API client**

Create `frontend/lib/api/overviewAnalysis.ts`:

```typescript
import { apiFetch } from "@/lib/api"

export interface AnalysisInsight {
  type: "info" | "warning" | "critical"
  title: string
  message: string
}

export interface OverviewAnalysisResult {
  id: string
  score: number
  grade: "A" | "B" | "C" | "D"
  portfolio_adherence_pct: number
  health: "GOOD" | "FAIR" | "POOR"
  insights: AnalysisInsight[]
  top_action: string
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  cost_usd: number
  cost_thb: number
  created_at: string
}

export interface ConfirmationRequired {
  requires_confirmation: true
  last_analyzed_minutes_ago: number
}

export async function triggerOverviewAnalysis(force = false): Promise<OverviewAnalysisResult | ConfirmationRequired> {
  return apiFetch(`/overview/ai-analysis${force ? "?force=true" : ""}`, { method: "POST" })
}

export async function getLatestOverviewAnalysis(): Promise<OverviewAnalysisResult | null> {
  return apiFetch("/overview/ai-analysis/latest")
}
```

- [ ] **Step 2: Create AIAnalysisCard component**

Create `frontend/components/overview/AIAnalysisCard.tsx`:

```tsx
"use client"

import { useState } from "react"
import { formatDistanceToNow } from "date-fns"
import { AlertTriangle, CheckCircle, Info, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  OverviewAnalysisResult,
  ConfirmationRequired,
  getLatestOverviewAnalysis,
  triggerOverviewAnalysis,
} from "@/lib/api/overviewAnalysis"

const INSIGHT_ICONS = {
  info: <Info className="h-4 w-4 text-blue-500" />,
  warning: <AlertTriangle className="h-4 w-4 text-yellow-500" />,
  critical: <AlertTriangle className="h-4 w-4 text-red-500" />,
}

const GRADE_COLORS: Record<string, string> = {
  A: "bg-green-100 text-green-800",
  B: "bg-blue-100 text-blue-800",
  C: "bg-yellow-100 text-yellow-800",
  D: "bg-red-100 text-red-800",
}

interface Props {
  initial: OverviewAnalysisResult | null
}

export function AIAnalysisCard({ initial }: Props) {
  const [analysis, setAnalysis] = useState<OverviewAnalysisResult | null>(initial)
  const [loading, setLoading] = useState(false)
  const [confirmState, setConfirmState] = useState<ConfirmationRequired | null>(null)

  async function handleAnalyze(force = false) {
    setLoading(true)
    try {
      const result = await triggerOverviewAnalysis(force)
      if ("requires_confirmation" in result) {
        setConfirmState(result)
      } else {
        setAnalysis(result)
        setConfirmState(null)
      }
    } finally {
      setLoading(false)
    }
  }

  if (!analysis) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            AI Portfolio Analysis
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4 py-8 text-center">
          <p className="text-muted-foreground text-sm">
            Get AI-powered guidance on your portfolio health, allocation, and next steps.
          </p>
          <Button onClick={() => handleAnalyze(false)} disabled={loading}>
            {loading ? "Analyzing…" : "Analyze My Portfolio"}
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-5 w-5" />
          AI Portfolio Analysis
        </CardTitle>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {formatDistanceToNow(new Date(analysis.created_at), { addSuffix: true })}
          </span>
          {confirmState ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                Analyzed {confirmState.last_analyzed_minutes_ago} min ago. Re-analyze?
              </span>
              <Button size="sm" variant="outline" onClick={() => setConfirmState(null)}>Cancel</Button>
              <Button size="sm" onClick={() => handleAnalyze(true)} disabled={loading}>Confirm</Button>
            </div>
          ) : (
            <Button size="sm" variant="outline" onClick={() => handleAnalyze(false)} disabled={loading}>
              {loading ? "Analyzing…" : "Re-analyze"}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold">{analysis.score}/100</span>
          <Badge className={GRADE_COLORS[analysis.grade]}>Grade {analysis.grade}</Badge>
          <Badge variant="outline">Adherence {analysis.portfolio_adherence_pct}%</Badge>
        </div>

        <div className="space-y-2">
          {analysis.insights.map((insight, i) => (
            <div key={i} className="flex items-start gap-2">
              {INSIGHT_ICONS[insight.type]}
              <div>
                <span className="text-sm font-medium">{insight.title}</span>
                <span className="text-sm text-muted-foreground"> — {insight.message}</span>
              </div>
            </div>
          ))}
        </div>

        {analysis.top_action && (
          <div className="rounded-md bg-muted p-3 text-sm">
            <span className="font-medium">Top action: </span>
            {analysis.top_action}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
```

---

### Task 7: Add AIAnalysisCard to Overview Page

**Files:**
- Modify: `frontend/app/(auth)/overview/page.tsx`

- [ ] **Step 1: Fetch latest analysis server-side and render card**

In `frontend/app/(auth)/overview/page.tsx`, add:

```tsx
import { AIAnalysisCard } from "@/components/overview/AIAnalysisCard"
import { getLatestOverviewAnalysis } from "@/lib/api/overviewAnalysis"

// Inside the page component (server component), fetch initial data:
const latestAnalysis = await getLatestOverviewAnalysis()

// In JSX, add at the bottom of the overview sections:
<AIAnalysisCard initial={latestAnalysis} />
```

- [ ] **Step 2: Verify in browser**

```bash
cd frontend && npm run dev
```

Navigate to Overview page. Verify:
- Empty state shown when no analysis exists
- "Analyze My Portfolio" button triggers POST and renders results
- Re-analyze within 30 min shows confirmation inline
- `?force=true` call bypasses guard and shows fresh result
