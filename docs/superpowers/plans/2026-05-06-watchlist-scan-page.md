# Watchlist Scan + Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add on-demand AI watchlist scanning (verdict + suggested buy price), AI ticker discovery (suggest new assets), and a full watchlist management page.

**Architecture:** Two new ARQ jobs (`job_scan_watchlist_item` / `job_scan_watchlist_batch`, `job_discover_watchlist`) use `LLMGateway` for LLM calls — this automatically writes `LLMCallLog` entries and uses feature-level config from Settings → AI. Verdicts stored in existing `ai_analyses` table. AI suggestions stored in new `watchlist_suggestions` table. Frontend page at `/watchlist` already has a sidebar nav link (`Star` icon) — just needs the page file.

**Tech Stack:** FastAPI + SQLAlchemy async + ARQ + Pydantic v2 + Next.js 15 App Router + shadcn/ui + `api` client (`@/lib/api` — has `get`, `post`, `patch`, `delete`)

---

## File Map

**New:**

- `backend/app/models/watchlist_suggestion.py`
- `backend/alembic/versions/017_watchlist_suggestion.py`
- `backend/worker/jobs/watchlist_scan.py`
- `backend/worker/jobs/watchlist_discover.py`
- `frontend/lib/services/watchlist.ts`
- `frontend/app/(auth)/watchlist/page.tsx`

**Modified:**

- `backend/app/models/feature_llm_config.py` — add 2 keys to FEATURE_KEYS
- `backend/app/services/llm_gateway.py` — add 2 keys to FEATURE_KEYS, DEFAULT_SYSTEM_PROMPTS, HUMAN_PROMPTS
- `backend/app/schemas/watchlist.py` — extend WatchlistItemOut, add WatchlistSuggestionOut
- `backend/app/api/watchlist.py` — add scan/discover/suggestion endpoints + update list query
- `backend/worker/main.py` — register 3 new jobs
- `frontend/lib/services/feature-llm-config.ts` — add 2 feature labels

---

### Task 1: WatchlistSuggestion model and migration

**Files:**

- Create: `backend/app/models/watchlist_suggestion.py`
- Create: `backend/alembic/versions/017_watchlist_suggestion.py`

- [ ] **Step 1: Create the model**

Create `backend/app/models/watchlist_suggestion.py`:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WatchlistSuggestion(Base):
    __tablename__ = "watchlist_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    verdict: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Create the migration**

Create `backend/alembic/versions/017_watchlist_suggestion.py`:

```python
"""watchlist_suggestion table

Revision ID: 017
Revises: 016
Create Date: 2026-05-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("suggested_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("verdict", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_watchlist_suggestions_user_id", "watchlist_suggestions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_watchlist_suggestions_user_id", table_name="watchlist_suggestions")
    op.drop_table("watchlist_suggestions")
```

- [ ] **Step 3: Run migration**

```bash
docker compose exec api alembic upgrade head
```

Expected output contains: `Running upgrade 016 -> 017, watchlist_suggestion table`

```bash
docker compose exec db psql -U zentri -c "\d watchlist_suggestions"
```

Expected: table with columns id, user_id, symbol, asset_id, reasoning, suggested_price, verdict, status, created_at.

---

### Task 2: Register new feature keys and prompts

**Files:**

- Modify: `backend/app/models/feature_llm_config.py`
- Modify: `backend/app/services/llm_gateway.py`

- [ ] **Step 1: Update FEATURE_KEYS in feature_llm_config.py**

In `backend/app/models/feature_llm_config.py`, replace the `FEATURE_KEYS` tuple:

```python
FEATURE_KEYS = (
    "import_translator",
    "transaction_classifier",
    "portfolio_analysis",
    "chat",
    "watchlist_scan",
    "watchlist_discovery",
)
```

- [ ] **Step 2: Update FEATURE_KEYS in llm_gateway.py**

In `backend/app/services/llm_gateway.py`, replace the `FEATURE_KEYS` tuple (same location near the top):

```python
FEATURE_KEYS = (
    "import_translator",
    "transaction_classifier",
    "portfolio_analysis",
    "chat",
    "watchlist_scan",
    "watchlist_discovery",
)
```

- [ ] **Step 3: Add system prompts to DEFAULT_SYSTEM_PROMPTS**

In `backend/app/services/llm_gateway.py`, add these two entries to the `DEFAULT_SYSTEM_PROMPTS` dict (after the last existing entry, before the closing `}`):

```python
    "watchlist_scan": (
        "You are a financial analyst evaluating an asset as a potential buy opportunity. "
        "The user does not currently hold this asset. Analyze the recent price history and research context. "
        "Respond ONLY with valid JSON in this exact format:\n"
        "{\"verdict\": \"BUY\" | \"SELL\" | \"HOLD\", \"suggested_price\": <number or null>, "
        "\"reasoning\": \"<2-3 sentence explanation>\"}\n"
        "Do not include any text outside the JSON object."
    ),
    "watchlist_discovery": (
        "You are a portfolio advisor. Based on the user's current holdings, suggest assets they should consider watching. "
        "Respond ONLY with a valid JSON array in this exact format:\n"
        "[{\"symbol\": \"<TICKER>\", \"verdict\": \"BUY\" | \"SELL\" | \"HOLD\", "
        "\"suggested_price\": <number or null>, \"reasoning\": \"<2-3 sentences>\"}]\n"
        "Suggest exactly 3 to 5 assets not already in the portfolio or watchlist. "
        "Do not include any text outside the JSON array."
    ),
```

- [ ] **Step 4: Add human prompts to HUMAN_PROMPTS**

In `backend/app/services/llm_gateway.py`, add these two entries to the `HUMAN_PROMPTS` dict (after the last existing entry, before the closing `}`):

```python
    "watchlist_scan": (
        "Asset: {symbol}\n\n"
        "Recent price history (last 10 days):\n{prices_txt}\n\n"
        "Research context:\n{rag_context}\n\n"
        "Should I buy this asset? Provide your JSON verdict."
    ),
    "watchlist_discovery": (
        "Current portfolio holdings:\n{holdings_txt}\n\n"
        "Already on watchlist (exclude these):\n{watchlist_txt}\n\n"
        "Suggest 3-5 assets worth watching based on the portfolio above. Respond with JSON array."
    ),
```

- [ ] **Step 5: Verify no import errors**

```bash
docker compose exec api python -c "
from app.services.llm_gateway import FEATURE_KEYS, HUMAN_PROMPTS, DEFAULT_SYSTEM_PROMPTS
assert 'watchlist_scan' in FEATURE_KEYS
assert 'watchlist_discovery' in FEATURE_KEYS
assert 'watchlist_scan' in HUMAN_PROMPTS
assert 'watchlist_discovery' in HUMAN_PROMPTS
print('OK')
"
```

Expected: `OK`

---

### Task 3: Extend schemas and watchlist list endpoint

**Files:**

- Modify: `backend/app/schemas/watchlist.py`
- Modify: `backend/app/api/watchlist.py`

- [ ] **Step 1: Extend schemas**

Replace all contents of `backend/app/schemas/watchlist.py`:

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AssetSummary(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    currency: str
    model_config = ConfigDict(from_attributes=True)


class WatchlistItemCreate(BaseModel):
    asset_id: uuid.UUID
    target_price: Decimal | None = None
    currency: str = "USD"
    notes: str | None = None


class WatchlistItemUpdate(BaseModel):
    target_price: Decimal | None = None
    notes: str | None = None
    alert_enabled: bool | None = None


class WatchlistItemOut(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    target_price: Decimal | None
    currency: str
    notes: str | None
    alert_enabled: bool
    alerted_at: datetime | None
    created_at: datetime
    asset: AssetSummary
    current_price: Decimal | None
    pct_from_target: float | None
    last_verdict: str | None = None
    ai_suggested_price: Decimal | None = None
    last_scanned_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class WatchlistSuggestionOut(BaseModel):
    id: uuid.UUID
    symbol: str
    asset_id: uuid.UUID | None
    reasoning: str
    suggested_price: Decimal | None
    verdict: str
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 2: Add AIAnalysis import to watchlist.py**

At the top of `backend/app/api/watchlist.py`, add:

```python
from app.models.ai_analysis import AIAnalysis
```

- [ ] **Step 3: Replace \_item_to_out to populate new fields**

In `backend/app/api/watchlist.py`, replace the `_item_to_out` function:

```python
async def _item_to_out(db: AsyncSession, item: WatchlistItem) -> WatchlistItemOut:
    asset = (await db.execute(select(Asset).where(Asset.id == item.asset_id))).scalar_one()
    price_row = (
        await db.execute(
            select(Price)
            .where(Price.asset_id == item.asset_id)
            .order_by(Price.timestamp.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    current_price = price_row.close if price_row else None
    pct = None
    if current_price is not None and item.target_price:
        pct = float((current_price - item.target_price) / item.target_price * 100)

    analysis = (
        await db.execute(
            select(AIAnalysis)
            .where(AIAnalysis.asset_id == item.asset_id)
            .order_by(AIAnalysis.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return WatchlistItemOut(
        id=item.id,
        asset_id=item.asset_id,
        target_price=item.target_price,
        currency=item.currency,
        notes=item.notes,
        alert_enabled=item.alert_enabled,
        alerted_at=item.alerted_at,
        created_at=item.created_at,
        asset=AssetSummary(id=asset.id, symbol=asset.symbol, name=asset.name, currency=asset.currency),
        current_price=current_price,
        pct_from_target=pct,
        last_verdict=analysis.verdict if analysis else None,
        ai_suggested_price=analysis.target_price if analysis else None,
        last_scanned_at=analysis.created_at if analysis else None,
    )
```

- [ ] **Step 4: Replace list_watchlist to batch-fetch analysis**

In `backend/app/api/watchlist.py`, replace the `list_watchlist` function:

```python
@router.get("", response_model=list[WatchlistItemOut])
async def list_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    latest_ts = (
        select(Price.asset_id, func.max(Price.timestamp).label("max_ts"))
        .group_by(Price.asset_id)
        .subquery("latest_ts")
    )
    stmt = (
        select(WatchlistItem, Asset, Price)
        .join(Asset, WatchlistItem.asset_id == Asset.id)
        .outerjoin(latest_ts, WatchlistItem.asset_id == latest_ts.c.asset_id)
        .outerjoin(
            Price,
            and_(
                Price.asset_id == WatchlistItem.asset_id,
                Price.timestamp == latest_ts.c.max_ts,
            ),
        )
        .where(WatchlistItem.user_id == current_user.id)
        .order_by(WatchlistItem.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    asset_ids = [row[1].id for row in rows]
    analyses: dict[uuid.UUID, AIAnalysis] = {}
    if asset_ids:
        latest_a_ts = (
            select(AIAnalysis.asset_id, func.max(AIAnalysis.created_at).label("max_ts"))
            .where(AIAnalysis.asset_id.in_(asset_ids))
            .group_by(AIAnalysis.asset_id)
            .subquery("latest_a_ts")
        )
        for a in (
            await db.execute(
                select(AIAnalysis).join(
                    latest_a_ts,
                    and_(
                        AIAnalysis.asset_id == latest_a_ts.c.asset_id,
                        AIAnalysis.created_at == latest_a_ts.c.max_ts,
                    ),
                )
            )
        ).scalars().all():
            analyses[a.asset_id] = a

    out = []
    for item, asset, price in rows:
        current_price = price.close if price else None
        pct = None
        if current_price is not None and item.target_price:
            pct = float((current_price - item.target_price) / item.target_price * 100)
        analysis = analyses.get(asset.id)
        out.append(
            WatchlistItemOut(
                id=item.id,
                asset_id=item.asset_id,
                target_price=item.target_price,
                currency=item.currency,
                notes=item.notes,
                alert_enabled=item.alert_enabled,
                alerted_at=item.alerted_at,
                created_at=item.created_at,
                asset=AssetSummary(id=asset.id, symbol=asset.symbol, name=asset.name, currency=asset.currency),
                current_price=current_price,
                pct_from_target=pct,
                last_verdict=analysis.verdict if analysis else None,
                ai_suggested_price=analysis.target_price if analysis else None,
                last_scanned_at=analysis.created_at if analysis else None,
            )
        )
    return out
```

- [ ] **Step 5: Verify imports**

```bash
docker compose exec api python -c "from app.api.watchlist import router; print('OK')"
```

Expected: `OK`

---

### Task 4: ARQ job — scan watchlist items

**Files:**

- Create: `backend/worker/jobs/watchlist_scan.py`

- [ ] **Step 1: Create the job file**

Create `backend/worker/jobs/watchlist_scan.py`:

````python
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.asset import Asset
from app.models.price import Price
from app.models.watchlist_item import WatchlistItem
from app.services.llm_gateway import LLMGateway
from app.services.pipeline import create_log, finish_log
from app.services.rag_service import get_or_create_collection, search

logger = get_logger(__name__)


def _parse_scan_response(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        data = json.loads(text)
        if data.get("verdict") not in ("BUY", "SELL", "HOLD"):
            return None
        return data
    except (json.JSONDecodeError, AttributeError):
        return None


async def job_scan_watchlist_item(ctx: dict, item_id: str, user_id: str) -> dict:
    """ARQ job: run AI analysis on a single watchlist item."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "watchlist_scan")
        try:
            item = (await db.execute(
                select(WatchlistItem).where(WatchlistItem.id == uuid.UUID(item_id))
            )).scalar_one_or_none()
            if not item:
                raise ValueError(f"WatchlistItem {item_id} not found")

            asset = (await db.execute(
                select(Asset).where(Asset.id == item.asset_id)
            )).scalar_one()

            since = datetime.now(timezone.utc) - timedelta(days=30)
            prices = (await db.execute(
                select(Price)
                .where(Price.asset_id == asset.id, Price.timestamp >= since)
                .order_by(desc(Price.timestamp))
                .limit(10)
            )).scalars().all()

            prices_txt = (
                "\n".join(f"{p.timestamp.date()}: close={p.close}" for p in prices)
                if prices else "No recent price history available."
            )

            collection = get_or_create_collection(asset.symbol)
            rag_chunks = search(collection, query=f"{asset.symbol} financial analysis outlook")
            rag_context = "\n\n---\n\n".join(rag_chunks) if rag_chunks else "No research documents available."

            gateway = LLMGateway(db)
            content = await gateway.complete(
                "watchlist_scan",
                uuid.UUID(user_id),
                {"symbol": asset.symbol, "prices_txt": prices_txt, "rag_context": rag_context},
            )
            parsed = _parse_scan_response(content)
            if parsed is None:
                raise ValueError(f"LLM returned malformed JSON: {content[:200]}")

            analysis = AIAnalysis(
                asset_id=asset.id,
                job_id=str(log.id),
                verdict=parsed["verdict"],
                target_price=parsed.get("suggested_price"),
                reasoning=parsed["reasoning"],
                provider="llm_gateway",
                model="watchlist_scan",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0,
            )
            db.add(analysis)
            await db.commit()
            await finish_log(db, log, success=True)
            logger.info("watchlist_scan done item=%s verdict=%s", item_id, parsed["verdict"])
            return {"verdict": parsed["verdict"], "analysis_id": str(analysis.id)}
        except Exception as e:
            logger.exception("job_scan_watchlist_item failed item=%s: %s", item_id, e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_scan_watchlist_batch(ctx: dict) -> dict:
    """ARQ job: enqueue scan jobs for every watchlist item."""
    from arq.connections import ArqRedis

    SessionLocal: async_sessionmaker = ctx["session_factory"]
    redis: ArqRedis = ctx["redis"]

    async with SessionLocal() as db:
        items = (await db.execute(select(WatchlistItem))).scalars().all()

    count = 0
    for item in items:
        await redis.enqueue_job("job_scan_watchlist_item", str(item.id), str(item.user_id))
        count += 1

    logger.info("watchlist batch scan: queued %d items", count)
    return {"queued": count}
````

- [ ] **Step 2: Verify import**

```bash
docker compose exec api python -c "from worker.jobs.watchlist_scan import job_scan_watchlist_item, job_scan_watchlist_batch; print('OK')"
```

Expected: `OK`

---

### Task 5: ARQ job — discover new tickers

**Files:**

- Create: `backend/worker/jobs/watchlist_discover.py`

- [ ] **Step 1: Create the job file**

Create `backend/worker/jobs/watchlist_discover.py`:

````python
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.holding import Holding
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.models.watchlist_suggestion import WatchlistSuggestion
from app.services.llm_gateway import LLMGateway
from app.services.pipeline import create_log, finish_log

logger = get_logger(__name__)


def _parse_discovery_response(text: str) -> list[dict] | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        data = json.loads(text)
        if not isinstance(data, list):
            return None
        valid = [
            item for item in data
            if item.get("verdict") in ("BUY", "SELL", "HOLD")
            and item.get("symbol")
            and item.get("reasoning")
        ]
        return valid or None
    except (json.JSONDecodeError, AttributeError):
        return None


async def job_discover_watchlist(ctx: dict) -> dict:
    """ARQ job: ask LLM to suggest new tickers based on portfolio, save as WatchlistSuggestion rows."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "watchlist_discovery")
        try:
            user = (await db.execute(select(User).limit(1))).scalar_one_or_none()
            if not user:
                raise ValueError("No user found")

            holdings_rows = (await db.execute(
                select(Holding, Asset).join(Asset, Holding.asset_id == Asset.id)
            )).all()
            holdings_txt = (
                "\n".join(f"- {asset.symbol} ({asset.name}): {h.quantity} units" for h, asset in holdings_rows)
                if holdings_rows else "No holdings yet."
            )
            portfolio_symbols = {asset.symbol for _, asset in holdings_rows}

            watchlist_rows = (await db.execute(
                select(WatchlistItem, Asset)
                .join(Asset, WatchlistItem.asset_id == Asset.id)
                .where(WatchlistItem.user_id == user.id)
            )).all()
            watchlist_symbols = {asset.symbol for _, asset in watchlist_rows}
            watchlist_txt = ", ".join(watchlist_symbols) if watchlist_symbols else "None"

            pending_symbols = set(
                (await db.execute(
                    select(WatchlistSuggestion.symbol).where(
                        WatchlistSuggestion.user_id == user.id,
                        WatchlistSuggestion.status == "pending",
                    )
                )).scalars().all()
            )

            gateway = LLMGateway(db)
            content = await gateway.complete(
                "watchlist_discovery",
                user.id,
                {"holdings_txt": holdings_txt, "watchlist_txt": watchlist_txt},
            )
            parsed = _parse_discovery_response(content)
            if parsed is None:
                raise ValueError(f"LLM returned malformed JSON: {content[:200]}")

            saved = 0
            for item in parsed:
                sym = item["symbol"].upper()
                if sym in portfolio_symbols or sym in watchlist_symbols or sym in pending_symbols:
                    continue

                asset_row = (await db.execute(
                    select(Asset).where(Asset.symbol == sym)
                )).scalar_one_or_none()

                db.add(WatchlistSuggestion(
                    user_id=user.id,
                    symbol=sym,
                    asset_id=asset_row.id if asset_row else None,
                    reasoning=item["reasoning"],
                    suggested_price=item.get("suggested_price"),
                    verdict=item["verdict"],
                    status="pending",
                ))
                saved += 1

            await db.commit()
            await finish_log(db, log, success=True)
            logger.info("watchlist_discover done: %d suggestions saved", saved)
            return {"suggestions_saved": saved}
        except Exception as e:
            logger.exception("job_discover_watchlist failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
````

- [ ] **Step 2: Verify import**

```bash
docker compose exec api python -c "from worker.jobs.watchlist_discover import job_discover_watchlist; print('OK')"
```

Expected: `OK`

---

### Task 6: New watchlist API endpoints

**Files:**

- Modify: `backend/app/api/watchlist.py`

- [ ] **Step 1: Add imports**

At the top of `backend/app/api/watchlist.py`, add:

```python
from arq.connections import RedisSettings, create_pool
from app.core.config import settings
from app.models.watchlist_suggestion import WatchlistSuggestion
from app.schemas.watchlist import WatchlistSuggestionOut
```

- [ ] **Step 2: Add suggestion ownership helper**

After the existing `_get_owned_item` function, add:

```python
async def _get_owned_suggestion(
    db: AsyncSession, suggestion_id: uuid.UUID, user_id: uuid.UUID
) -> WatchlistSuggestion:
    result = await db.execute(
        select(WatchlistSuggestion).where(
            WatchlistSuggestion.id == suggestion_id,
            WatchlistSuggestion.user_id == user_id,
        )
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return suggestion
```

- [ ] **Step 3: Append scan + discover endpoints**

Append to the end of `backend/app/api/watchlist.py`:

```python
@router.post("/{item_id}/scan")
async def trigger_item_scan(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await _get_owned_item(db, item_id, current_user.id)
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_scan_watchlist_item", str(item.id), str(current_user.id))
        await redis.aclose()
        logger.info("watchlist scan enqueued item=%s job=%s", item_id, job.job_id if job else None)
    except Exception:
        logger.exception("Failed to enqueue scan for item %s", item_id)
    return {"queued": True, "item_id": str(item_id)}


@router.post("/scan-all")
async def trigger_scan_all(current_user: User = Depends(get_current_user)):
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_scan_watchlist_batch")
        await redis.aclose()
        logger.info("watchlist batch scan enqueued job=%s", job.job_id if job else None)
    except Exception:
        logger.exception("Failed to enqueue batch scan")
    return {"queued": True}


@router.post("/discover")
async def trigger_discover(current_user: User = Depends(get_current_user)):
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_discover_watchlist")
        await redis.aclose()
        logger.info("watchlist discovery enqueued job=%s", job.job_id if job else None)
    except Exception:
        logger.exception("Failed to enqueue discovery")
    return {"queued": True}


@router.get("/suggestions", response_model=list[WatchlistSuggestionOut])
async def list_suggestions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WatchlistSuggestion)
        .where(
            WatchlistSuggestion.user_id == current_user.id,
            WatchlistSuggestion.status == "pending",
        )
        .order_by(WatchlistSuggestion.created_at.desc())
    )
    return result.scalars().all()


@router.post("/suggestions/{suggestion_id}/accept", response_model=WatchlistItemOut, status_code=201)
async def accept_suggestion(
    suggestion_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    suggestion = await _get_owned_suggestion(db, suggestion_id, current_user.id)

    asset_id = suggestion.asset_id
    if asset_id is None:
        asset_row = (await db.execute(
            select(Asset).where(Asset.symbol == suggestion.symbol.upper())
        )).scalar_one_or_none()
        if asset_row is None:
            raise HTTPException(status_code=404, detail=f"Asset '{suggestion.symbol}' not found in database")
        asset_id = asset_row.id

    existing = (await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == current_user.id,
            WatchlistItem.asset_id == asset_id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Asset already in watchlist")

    item = WatchlistItem(
        user_id=current_user.id,
        asset_id=asset_id,
        target_price=suggestion.suggested_price,
        alert_enabled=suggestion.suggested_price is not None,
    )
    db.add(item)
    suggestion.status = "accepted"
    await db.commit()
    await db.refresh(item)
    logger.info("Suggestion accepted: %s → WatchlistItem", suggestion.symbol)
    return await _item_to_out(db, item)


@router.post("/suggestions/{suggestion_id}/dismiss", status_code=204)
async def dismiss_suggestion(
    suggestion_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    suggestion = await _get_owned_suggestion(db, suggestion_id, current_user.id)
    suggestion.status = "dismissed"
    await db.commit()
```

- [ ] **Step 4: Verify API loads**

```bash
docker compose exec api python -c "from app.api.watchlist import router; paths = [r.path for r in router.routes]; print(paths)"
```

Expected output includes: `/watchlist/{item_id}/scan`, `/watchlist/scan-all`, `/watchlist/discover`, `/watchlist/suggestions`, `/watchlist/suggestions/{suggestion_id}/accept`, `/watchlist/suggestions/{suggestion_id}/dismiss`

---

### Task 7: Register jobs in worker

**Files:**

- Modify: `backend/worker/main.py`

- [ ] **Step 1: Add imports and register jobs**

In `backend/worker/main.py`, add after the existing imports:

```python
from worker.jobs.watchlist_discover import job_discover_watchlist
from worker.jobs.watchlist_scan import job_scan_watchlist_batch, job_scan_watchlist_item
```

Then in `WorkerSettings.functions`, add the three new jobs:

```python
    functions = [
        job_fetch_prices_us,
        job_fetch_prices_crypto,
        job_fetch_price_gold,
        job_fetch_benchmark_prices,
        job_ingest_document,
        job_run_analysis,
        job_snapshot_net_worth,
        job_fetch_dividends,
        job_check_watchlist_alerts,
        job_scan_watchlist_item,
        job_scan_watchlist_batch,
        job_discover_watchlist,
    ]
```

- [ ] **Step 2: Verify worker loads**

```bash
docker compose exec worker python -c "from worker.main import WorkerSettings; print('functions:', len(WorkerSettings.functions))"
```

Expected: `functions: 12`

---

### Task 8: Frontend service

**Files:**

- Create: `frontend/lib/services/watchlist.ts`

- [ ] **Step 1: Create the service**

Create `frontend/lib/services/watchlist.ts`:

```typescript
import { api } from "@/lib/api";

export interface WatchlistAsset {
  id: string;
  symbol: string;
  name: string;
  currency: string;
}

export interface WatchlistItem {
  id: string;
  asset_id: string;
  target_price: string | null;
  currency: string;
  notes: string | null;
  alert_enabled: boolean;
  alerted_at: string | null;
  created_at: string;
  asset: WatchlistAsset;
  current_price: string | null;
  pct_from_target: number | null;
  last_verdict: "BUY" | "SELL" | "HOLD" | null;
  ai_suggested_price: string | null;
  last_scanned_at: string | null;
}

export interface WatchlistSuggestion {
  id: string;
  symbol: string;
  asset_id: string | null;
  reasoning: string;
  suggested_price: string | null;
  verdict: "BUY" | "SELL" | "HOLD";
  status: "pending" | "accepted" | "dismissed";
  created_at: string;
}

export async function listWatchlist(): Promise<WatchlistItem[]> {
  const r = await api.get("/api/v1/watchlist");
  if (!r.ok) throw new Error("Failed to fetch watchlist");
  return r.json();
}

export async function addToWatchlist(body: {
  asset_id: string;
  target_price?: string | null;
  currency?: string;
  notes?: string | null;
}): Promise<WatchlistItem> {
  const r = await api.post("/api/v1/watchlist", body);
  if (!r.ok) throw new Error("Failed to add to watchlist");
  return r.json();
}

export async function updateWatchlistItem(
  id: string,
  patch: {
    target_price?: string | null;
    notes?: string | null;
    alert_enabled?: boolean;
  },
): Promise<WatchlistItem> {
  const r = await api.patch(`/api/v1/watchlist/${id}`, patch);
  if (!r.ok) throw new Error("Failed to update watchlist item");
  return r.json();
}

export async function deleteWatchlistItem(id: string): Promise<void> {
  await api.delete(`/api/v1/watchlist/${id}`);
}

export async function rearmWatchlistItem(id: string): Promise<WatchlistItem> {
  const r = await api.post(`/api/v1/watchlist/${id}/rearm`, {});
  if (!r.ok) throw new Error("Failed to rearm alert");
  return r.json();
}

export async function scanItem(id: string): Promise<void> {
  await api.post(`/api/v1/watchlist/${id}/scan`, {});
}

export async function scanAll(): Promise<void> {
  await api.post("/api/v1/watchlist/scan-all", {});
}

export async function discoverWatchlist(): Promise<void> {
  await api.post("/api/v1/watchlist/discover", {});
}

export async function listSuggestions(): Promise<WatchlistSuggestion[]> {
  const r = await api.get("/api/v1/watchlist/suggestions");
  if (!r.ok) throw new Error("Failed to fetch suggestions");
  return r.json();
}

export async function acceptSuggestion(id: string): Promise<WatchlistItem> {
  const r = await api.post(`/api/v1/watchlist/suggestions/${id}/accept`, {});
  if (!r.ok) throw new Error("Failed to accept suggestion");
  return r.json();
}

export async function dismissSuggestion(id: string): Promise<void> {
  await api.post(`/api/v1/watchlist/suggestions/${id}/dismiss`, {});
}
```

- [ ] **Step 2: Add feature labels**

In `frontend/lib/services/feature-llm-config.ts`, update `FEATURE_LABELS`:

```typescript
export const FEATURE_LABELS: Record<string, string> = {
  import_translator: "Import Translator",
  transaction_classifier: "Transaction Classifier",
  portfolio_analysis: "Portfolio Analysis",
  chat: "Chat Assistant",
  watchlist_scan: "Watchlist Scanner",
  watchlist_discovery: "Watchlist Discovery",
};
```

---

### Task 9: Watchlist page

**Files:**

- Create: `frontend/app/(auth)/watchlist/page.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/app/(auth)/watchlist/page.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bell,
  BellOff,
  Check,
  Plus,
  Scan,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  acceptSuggestion,
  addToWatchlist,
  deleteWatchlistItem,
  discoverWatchlist,
  dismissSuggestion,
  listSuggestions,
  listWatchlist,
  rearmWatchlistItem,
  scanAll,
  scanItem,
  updateWatchlistItem,
  type WatchlistItem,
  type WatchlistSuggestion,
} from "@/lib/services/watchlist";

const VERDICT_STYLE: Record<string, string> = {
  BUY: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  SELL: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  HOLD: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
};

type AssetResult = {
  id: string;
  symbol: string;
  name: string;
  currency: string;
};

function AddDialog({
  open,
  onClose,
  onAdded,
}: {
  open: boolean;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AssetResult[]>([]);
  const [selected, setSelected] = useState<AssetResult | null>(null);
  const [targetPrice, setTargetPrice] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (!query) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      const r = await api.get(
        `/api/v1/assets/search?q=${encodeURIComponent(query)}`,
      );
      if (r.ok) setResults(await r.json());
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  const handleAdd = async () => {
    if (!selected) return;
    setAdding(true);
    try {
      await addToWatchlist({
        asset_id: selected.id,
        target_price: targetPrice || null,
      });
      toast.success(`${selected.symbol} added to watchlist`);
      onAdded();
      onClose();
      setQuery("");
      setSelected(null);
      setTargetPrice("");
    } catch {
      toast.error("Failed to add to watchlist");
    } finally {
      setAdding(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add to Watchlist</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <input
            className="w-full border rounded px-3 py-2 text-sm"
            placeholder="Search ticker or name…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelected(null);
            }}
          />
          {results.length > 0 && !selected && (
            <div className="border rounded divide-y max-h-48 overflow-y-auto">
              {results.map((a) => (
                <button
                  key={a.id}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-accent"
                  onClick={() => {
                    setSelected(a);
                    setQuery(a.symbol);
                    setResults([]);
                  }}
                >
                  <span className="font-medium">{a.symbol}</span>{" "}
                  <span className="text-muted-foreground">{a.name}</span>
                </button>
              ))}
            </div>
          )}
          {selected && (
            <div>
              <label className="text-xs text-muted-foreground block mb-1">
                Target price (optional)
              </label>
              <input
                type="number"
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="e.g. 150.00"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
              />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleAdd} disabled={!selected || adding}>
            {adding ? "Adding…" : "Add"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [suggestions, setSuggestions] = useState<WatchlistSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanningAll, setScanningAll] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [scanningId, setScanningId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    const [w, s] = await Promise.all([
      listWatchlist().catch(() => []),
      listSuggestions().catch(() => []),
    ]);
    setItems(w);
    setSuggestions(s);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const handleScanAll = async () => {
    setScanningAll(true);
    await scanAll();
    toast.success("Scan queued — results will appear shortly");
    setScanningAll(false);
    setTimeout(fetchAll, 5000);
  };

  const handleDiscover = async () => {
    setDiscovering(true);
    await discoverWatchlist();
    toast.success("Discovery queued — suggestions will appear shortly");
    setDiscovering(false);
    setTimeout(fetchAll, 6000);
  };

  const handleScanItem = async (id: string) => {
    setScanningId(id);
    await scanItem(id);
    toast.success("Scan queued");
    setScanningId(null);
    setTimeout(fetchAll, 5000);
  };

  const handleApplyPrice = async (item: WatchlistItem) => {
    if (!item.ai_suggested_price) return;
    await updateWatchlistItem(item.id, {
      target_price: item.ai_suggested_price,
      alert_enabled: true,
    });
    toast.success("Target price set and alert enabled");
    fetchAll();
  };

  const handleToggleAlert = async (item: WatchlistItem) => {
    if (item.alerted_at && !item.alert_enabled) {
      await rearmWatchlistItem(item.id);
    } else {
      await updateWatchlistItem(item.id, {
        alert_enabled: !item.alert_enabled,
      });
    }
    fetchAll();
  };

  const handleDelete = async (id: string) => {
    await deleteWatchlistItem(id);
    toast.success("Removed from watchlist");
    fetchAll();
  };

  const handleAccept = async (s: WatchlistSuggestion) => {
    try {
      await acceptSuggestion(s.id);
      toast.success(`${s.symbol} added to watchlist`);
      fetchAll();
    } catch {
      toast.error("Failed to accept suggestion");
    }
  };

  const handleDismiss = async (id: string) => {
    await dismissSuggestion(id);
    setSuggestions((prev) => prev.filter((s) => s.id !== id));
  };

  return (
    <div className="p-6 space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Watchlist</h1>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleScanAll}
            disabled={scanningAll}
          >
            <Scan
              className={`h-4 w-4 mr-2 ${scanningAll ? "animate-pulse" : ""}`}
            />
            {scanningAll ? "Scanning…" : "Scan All"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDiscover}
            disabled={discovering}
          >
            <Sparkles
              className={`h-4 w-4 mr-2 ${discovering ? "animate-pulse" : ""}`}
            />
            {discovering ? "Discovering…" : "Discover New"}
          </Button>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add
          </Button>
        </div>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No items on your watchlist. Click Add to start watching an asset, or
          Discover New for AI suggestions.
        </p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ticker</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">Target</TableHead>
                <TableHead className="text-right">% to Target</TableHead>
                <TableHead>AI Verdict</TableHead>
                <TableHead className="text-right">AI Price</TableHead>
                <TableHead>Last Scanned</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="font-medium">{item.asset.symbol}</div>
                    <div className="text-xs text-muted-foreground">
                      {item.asset.name}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    {item.current_price
                      ? `$${parseFloat(item.current_price).toFixed(2)}`
                      : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    {item.target_price
                      ? `$${parseFloat(item.target_price).toFixed(2)}`
                      : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    {item.pct_from_target !== null ? (
                      <span
                        className={
                          item.pct_from_target <= 0
                            ? "text-green-600"
                            : "text-muted-foreground"
                        }
                      >
                        {item.pct_from_target > 0 ? "+" : ""}
                        {item.pct_from_target.toFixed(1)}%
                      </span>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell>
                    {item.last_verdict ? (
                      <span
                        className={`text-xs font-medium px-2 py-1 rounded-full ${VERDICT_STYLE[item.last_verdict]}`}
                      >
                        {item.last_verdict}
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {item.ai_suggested_price
                      ? `$${parseFloat(item.ai_suggested_price).toFixed(2)}`
                      : "—"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {item.last_scanned_at
                      ? new Date(item.last_scanned_at).toLocaleDateString()
                      : "Never"}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Scan"
                        disabled={scanningId === item.id}
                        onClick={() => handleScanItem(item.id)}
                      >
                        <Scan
                          className={`h-4 w-4 ${scanningId === item.id ? "animate-pulse" : ""}`}
                        />
                      </Button>
                      {item.ai_suggested_price && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-xs h-8 px-2"
                          title="Apply AI price as target alert"
                          onClick={() => handleApplyPrice(item)}
                        >
                          Apply
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        title={
                          item.alert_enabled ? "Disable alert" : "Enable alert"
                        }
                        onClick={() => handleToggleAlert(item)}
                      >
                        {item.alert_enabled ? (
                          <Bell className="h-4 w-4 text-blue-500" />
                        ) : (
                          <BellOff className="h-4 w-4 text-muted-foreground" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Remove"
                        onClick={() => handleDelete(item.id)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-500" />
            AI Suggestions
          </h2>
          <div className="grid gap-3">
            {suggestions.map((s) => (
              <div
                key={s.id}
                className="border rounded-lg p-4 flex items-start justify-between gap-4"
              >
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{s.symbol}</span>
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded-full ${VERDICT_STYLE[s.verdict]}`}
                    >
                      {s.verdict}
                    </span>
                    {s.suggested_price && (
                      <span className="text-xs text-muted-foreground">
                        suggested ${parseFloat(s.suggested_price).toFixed(2)}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{s.reasoning}</p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleAccept(s)}
                  >
                    <Check className="h-4 w-4 mr-1" />
                    Watch
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDismiss(s.id)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <AddDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onAdded={fetchAll}
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error|✓|Failed" | tail -20
```

Expected: build succeeds with no TypeScript errors in the watchlist page.

---

### Task 10: Smoke test

- [ ] **Step 1: Restart services**

```bash
docker compose restart api worker
```

- [ ] **Step 2: Check API docs for new endpoints**

Open `http://localhost:8000/docs` and verify these routes exist under the `watchlist` tag:

- `POST /api/v1/watchlist/{item_id}/scan`
- `POST /api/v1/watchlist/scan-all`
- `POST /api/v1/watchlist/discover`
- `GET /api/v1/watchlist/suggestions`
- `POST /api/v1/watchlist/suggestions/{suggestion_id}/accept`
- `POST /api/v1/watchlist/suggestions/{suggestion_id}/dismiss`

- [ ] **Step 3: Check watchlist list returns new fields**

```bash
curl -s http://localhost:8000/api/v1/watchlist \
  -H "Authorization: Bearer <token>" | python3 -m json.tool | grep -E "last_verdict|ai_suggested|last_scanned"
```

Expected: these keys appear (values may be null if no scan run yet).

- [ ] **Step 4: Open watchlist page in browser**

Navigate to `http://localhost:3000/watchlist`. Confirm:

- Page loads without console errors
- Table renders with verdict / AI price / Last Scanned columns
- Scan All, Discover New, Add buttons are present

- [ ] **Step 5: Configure LLM in Settings → AI**

Go to Settings → AI. Verify "Watchlist Scanner" and "Watchlist Discovery" appear as configurable features. Assign a provider and model to each.

- [ ] **Step 6: Test single item scan**

Add an asset to the watchlist (click Add → search → select). Then click the [Scan] icon on that row. Wait 5–10 seconds, refresh the page. The AI Verdict and AI Price columns should populate.

- [ ] **Step 7: Test batch scan**

Click "Scan All". A toast appears. After ~10s, refresh — all items should have updated verdict fields.

- [ ] **Step 8: Test discovery**

Click "Discover New". Wait ~10s, refresh — the "AI Suggestions" section appears with suggestion cards. Click [Watch] on one to accept it. Verify it moves into the My Watchlist table.

- [ ] **Step 9: Verify AI Usage logs**

Go to AI Usage page. Confirm new `watchlist_scan` and `watchlist_discovery` entries appear with token counts and costs.
