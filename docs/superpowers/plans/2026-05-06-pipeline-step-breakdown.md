# Pipeline Step Breakdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-step tracking to every pipeline job so the Pipeline Monitor page can expand each row to show real-time step-level progress, with full LLM token/cost/prompt/response detail for AI steps.

**Architecture:** New `pipeline_steps` table stores timestamped steps emitted by workers via `create_step`/`finish_step` service calls. The existing SSE stream is extended to include steps in each job payload. The frontend `JobsTable` becomes expandable, rendering a `StepList` component that shows live step progress every 3s.

**Tech Stack:** Python/FastAPI, SQLAlchemy (async), PostgreSQL/JSONB, Alembic, Next.js, React, TypeScript, TanStack Query

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/app/models/pipeline_step.py` | Create | ORM model for `pipeline_steps` table |
| `backend/app/models/pipeline_log.py` | Modify | Add `steps` relationship |
| `backend/alembic/versions/019_pipeline_steps.py` | Create | Create `pipeline_steps` table |
| `backend/app/schemas/pipeline.py` | Modify | Add `PipelineStepResponse`, extend `PipelineLogResponse` |
| `backend/app/services/pipeline.py` | Modify | Add `create_step`/`finish_step`, eager-load steps |
| `backend/app/services/llm_gateway.py` | Modify | Return `LLMGatewayResult` (content + usage) instead of bare `str` |
| `backend/app/api/pipeline.py` | Modify | SSE stream includes steps; response model uses updated schema |
| `backend/worker/jobs/price_fetch.py` | Modify | Emit `fetch_and_store` step per job |
| `backend/worker/jobs/watchlist_discover.py` | Modify | Emit `load_portfolio`, `llm_call`, `save_suggestions` steps |
| `backend/worker/jobs/watchlist_scan.py` | Modify | Emit `load_asset`, `rag_retrieval`, `llm_call`, `save_suggestion` steps |
| `backend/worker/jobs/run_analysis.py` | Modify | Emit `load_asset`, `rag_retrieval`, `llm_call`, `save_analysis` steps |
| `backend/worker/jobs/ingest_document.py` | Modify | Emit `load_document`, `chunk_text`, `embed_store` steps |
| `frontend/lib/services/pipeline.ts` | Modify | Add `PipelineStep` type, extend `PipelineJob` |
| `frontend/components/pipeline/StepList.tsx` | Create | Renders step list with LLM detail panels |
| `frontend/components/pipeline/JobsTable.tsx` | Modify | Expandable rows, chevron toggle, import `StepList` |

---

## Task 1: PipelineStep model + migration

**Files:**
- Create: `backend/app/models/pipeline_step.py`
- Modify: `backend/app/models/pipeline_log.py`
- Create: `backend/alembic/versions/019_pipeline_steps.py`

- [ ] **Step 1: Create the PipelineStep model**

Create `backend/app/models/pipeline_step.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pipeline_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_logs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("running", "done", "failed", name="pipeline_step_status_enum"),
        nullable=False,
        default="running",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    pipeline_log: Mapped["PipelineLog"] = relationship(  # type: ignore[name-defined]
        "PipelineLog", back_populates="steps"
    )
```

- [ ] **Step 2: Add `steps` relationship to PipelineLog**

Edit `backend/app/models/pipeline_log.py` — add import and relationship at the bottom of the class:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

JOB_TYPES = (
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark",
    "ingest_document", "run_analysis",
    "watchlist_discovery", "watchlist_scan",
)
JOB_STATUSES = ("queued", "running", "done", "failed")


class PipelineLog(Base):
    __tablename__ = "pipeline_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(
        Enum(*JOB_TYPES, name="job_type_enum"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(*JOB_STATUSES, name="job_status_enum"), nullable=False, default="queued"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["PipelineStep"]] = relationship(  # type: ignore[name-defined]
        "PipelineStep",
        back_populates="pipeline_log",
        order_by="PipelineStep.started_at",
        lazy="raise",
    )
```

- [ ] **Step 3: Create migration 019**

Create `backend/alembic/versions/019_pipeline_steps.py`:

```python
"""add pipeline_steps table

Revision ID: 019
Revises: 018
Create Date: 2026-05-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE pipeline_step_status_enum AS ENUM ('running', 'done', 'failed')"
    )
    op.create_table(
        "pipeline_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pipeline_log_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pipeline_logs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_name", sa.String, nullable=False),
        sa.Column(
            "status",
            sa.Enum("running", "done", "failed", name="pipeline_step_status_enum"),
            nullable=False,
            server_default="running",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_pipeline_steps_pipeline_log_id",
        "pipeline_steps",
        ["pipeline_log_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_steps_pipeline_log_id", "pipeline_steps")
    op.drop_table("pipeline_steps")
    op.execute("DROP TYPE pipeline_step_status_enum")
```

- [ ] **Step 4: Run migration in Docker**

```bash
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 018 -> 019`

- [ ] **Step 5: Verify table exists**

```bash
docker compose exec db psql -U zentri -d zentri -c "\d pipeline_steps"
```

Expected: table with columns `id`, `pipeline_log_id`, `step_name`, `status`, `started_at`, `finished_at`, `metadata`, `error_message`

---

## Task 2: Schema + service layer

**Files:**
- Modify: `backend/app/schemas/pipeline.py`
- Modify: `backend/app/services/pipeline.py`

- [ ] **Step 1: Write failing test for create_step/finish_step**

Add to `backend/tests/test_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_create_and_finish_step(db):
    from app.services.pipeline import create_log, create_step, finish_step

    log = await create_log(db, "price_fetch_us")
    step = await create_step(db, log.id, "fetch_and_store")
    assert step.status == "running"
    assert step.finished_at is None

    finished = await finish_step(db, step, success=True, metadata={"inserted": 42})
    assert finished.status == "done"
    assert finished.metadata == {"inserted": 42}
    assert finished.finished_at is not None


@pytest.mark.asyncio
async def test_list_logs_includes_steps(db):
    from app.services.pipeline import create_log, create_step, list_logs

    log = await create_log(db, "price_fetch_us")
    await create_step(db, log.id, "fetch_and_store")

    logs = await list_logs(db, limit=10)
    assert any(str(l.id) == str(log.id) for l in logs)
    matching = next(l for l in logs if str(l.id) == str(log.id))
    assert len(matching.steps) == 1
    assert matching.steps[0].step_name == "fetch_and_store"
```

- [ ] **Step 2: Run to verify failure**

```bash
docker compose exec backend pytest tests/test_pipeline.py::test_create_and_finish_step tests/test_pipeline.py::test_list_logs_includes_steps -v
```

Expected: `FAILED — create_step not found` or import error

- [ ] **Step 3: Update schema**

Replace `backend/app/schemas/pipeline.py`:

```python
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

JobType = Literal[
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark",
    "watchlist_discovery", "watchlist_scan",
    "run_analysis", "ingest_document",
]
JobStatus = Literal["queued", "running", "done", "failed"]
StepStatus = Literal["running", "done", "failed"]


class PipelineStepResponse(BaseModel):
    id: uuid.UUID
    pipeline_log_id: uuid.UUID
    step_name: str
    status: StepStatus
    started_at: datetime
    finished_at: datetime | None
    metadata: dict | None
    error_message: str | None

    model_config = {"from_attributes": True}


class PipelineLogResponse(BaseModel):
    id: uuid.UUID
    job_type: JobType
    status: JobStatus
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    steps: list[PipelineStepResponse] = []

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Update pipeline service**

Replace `backend/app/services/pipeline.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.pipeline_log import PipelineLog
from app.models.pipeline_step import PipelineStep

logger = get_logger(__name__)


async def create_log(db: AsyncSession, job_type: str) -> PipelineLog:
    log = PipelineLog(
        job_type=job_type,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    logger.info("pipeline job started job_type=%s id=%s", job_type, log.id)
    return log


async def finish_log(
    db: AsyncSession,
    log: PipelineLog,
    *,
    success: bool,
    error_message: str | None = None,
) -> PipelineLog:
    log.status = "done" if success else "failed"
    log.finished_at = datetime.now(timezone.utc)
    log.error_message = error_message
    await db.commit()
    await db.refresh(log)
    logger.info(
        "pipeline job finished job_type=%s status=%s id=%s",
        log.job_type, log.status, log.id,
    )
    return log


async def create_step(
    db: AsyncSession, pipeline_log_id: uuid.UUID, step_name: str
) -> PipelineStep:
    step = PipelineStep(
        pipeline_log_id=pipeline_log_id,
        step_name=step_name,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    logger.info("pipeline step started step=%s log_id=%s", step_name, pipeline_log_id)
    return step


async def finish_step(
    db: AsyncSession,
    step: PipelineStep,
    *,
    success: bool,
    metadata: dict | None = None,
    error: str | None = None,
) -> PipelineStep:
    step.status = "done" if success else "failed"
    step.finished_at = datetime.now(timezone.utc)
    step.metadata = metadata
    step.error_message = error
    await db.commit()
    await db.refresh(step)
    logger.info(
        "pipeline step finished step=%s status=%s", step.step_name, step.status
    )
    return step


async def list_logs(db: AsyncSession, limit: int = 50) -> list[PipelineLog]:
    result = await db.execute(
        select(PipelineLog)
        .options(selectinload(PipelineLog.steps))
        .order_by(desc(PipelineLog.started_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_log(db: AsyncSession, log_id: uuid.UUID) -> PipelineLog | None:
    result = await db.execute(
        select(PipelineLog)
        .options(selectinload(PipelineLog.steps))
        .where(PipelineLog.id == log_id)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 5: Run tests**

```bash
docker compose exec backend pytest tests/test_pipeline.py -v
```

Expected: all 5 tests PASS

---

## Task 3: LLMGateway returns usage

**Files:**
- Modify: `backend/app/services/llm_gateway.py`

- [ ] **Step 1: Add `LLMGatewayResult` dataclass**

At the top of `backend/app/services/llm_gateway.py`, after the imports, add:

```python
from dataclasses import dataclass

@dataclass
class LLMGatewayResult:
    content: str
    prompt: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cost_thb: float
    exchange_rate: float
    model: str
    provider: str
```

- [ ] **Step 2: Change `LLMGateway.complete()` return type**

In `LLMGateway.complete()`, replace the final `return response.content` with:

```python
        return LLMGatewayResult(
            content=response.content,
            prompt=human,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=float(response.cost_usd),
            cost_thb=cost_thb,
            exchange_rate=float(usd_thb) if usd_thb else 0.0,
            model=config.model,
            provider=provider.provider,
        )
```

Also update the method signature to `async def complete(self, ...) -> LLMGatewayResult:`.

- [ ] **Step 3: Update watchlist_discover caller**

In `backend/worker/jobs/watchlist_discover.py`, change:

```python
            content = await gateway.complete(
                "watchlist_discovery",
                user.id,
                {"holdings_txt": holdings_txt, "watchlist_txt": watchlist_txt},
            )
            logger.info("LLM watchlist_discovery response received, length=%d", len(content))

            parsed = _parse_discovery_response(content)
            if parsed is None:
                raise ValueError(f"LLM returned malformed JSON: {content[:200]}")
```

To:

```python
            llm_result = await gateway.complete(
                "watchlist_discovery",
                user.id,
                {"holdings_txt": holdings_txt, "watchlist_txt": watchlist_txt},
            )
            logger.info("LLM watchlist_discovery response received, length=%d", len(llm_result.content))

            parsed = _parse_discovery_response(llm_result.content)
            if parsed is None:
                raise ValueError(f"LLM returned malformed JSON: {llm_result.content[:200]}")
```

- [ ] **Step 4: Update watchlist_scan caller**

In `backend/worker/jobs/watchlist_scan.py`, change:

```python
            content = await gateway.complete(
                "watchlist_scan",
                uuid.UUID(user_id),
                {"symbol": asset.symbol, "prices_txt": prices_txt, "rag_context": rag_context},
            )
            parsed = _parse_scan_response(content)
            if parsed is None:
                raise ValueError(f"LLM returned malformed JSON: {content[:200]}")
```

To:

```python
            llm_result = await gateway.complete(
                "watchlist_scan",
                uuid.UUID(user_id),
                {"symbol": asset.symbol, "prices_txt": prices_txt, "rag_context": rag_context},
            )
            parsed = _parse_scan_response(llm_result.content)
            if parsed is None:
                raise ValueError(f"LLM returned malformed JSON: {llm_result.content[:200]}")
```

- [ ] **Step 5: Verify no broken imports**

```bash
docker compose exec backend python -c "from app.services.llm_gateway import LLMGateway, LLMGatewayResult; print('OK')"
```

Expected: `OK`

---

## Task 4: API — SSE includes steps

**Files:**
- Modify: `backend/app/api/pipeline.py`

- [ ] **Step 1: Update the SSE event generator**

In `backend/app/api/pipeline.py`, replace the `event_generator` function body inside `pipeline_stream`:

```python
    async def event_generator():
        while True:
            logs = await list_logs(db, limit=20)
            data = [
                {
                    "id": str(log.id),
                    "job_type": log.job_type,
                    "status": log.status,
                    "started_at": log.started_at.isoformat(),
                    "finished_at": log.finished_at.isoformat() if log.finished_at else None,
                    "error_message": log.error_message,
                    "steps": [
                        {
                            "id": str(s.id),
                            "pipeline_log_id": str(s.pipeline_log_id),
                            "step_name": s.step_name,
                            "status": s.status,
                            "started_at": s.started_at.isoformat(),
                            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                            "metadata": s.metadata,
                            "error_message": s.error_message,
                        }
                        for s in log.steps
                    ],
                }
                for log in logs
            ]
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(3)
```

- [ ] **Step 2: Verify the endpoint returns steps**

```bash
docker compose exec backend python -c "
import asyncio
from app.core.database import async_session_factory
from app.services.pipeline import list_logs

async def check():
    async with async_session_factory() as db:
        logs = await list_logs(db, limit=1)
        print('logs:', len(logs))
        if logs:
            print('steps:', logs[0].steps)

asyncio.run(check())
"
```

Expected: prints `logs: N` without raising `MissingGreenlet` or lazy-load errors

---

## Task 5: Instrument price_fetch workers

**Files:**
- Modify: `backend/worker/jobs/price_fetch.py`

- [ ] **Step 1: Update imports**

At the top of `backend/worker/jobs/price_fetch.py`, change:

```python
from app.services.pipeline import create_log, finish_log
```

To:

```python
from app.services.pipeline import create_log, finish_log, create_step, finish_step
```

- [ ] **Step 2: Instrument job_fetch_prices_us**

Replace the function body:

```python
async def job_fetch_prices_us(ctx: dict) -> dict:
    """ARQ job: fetch US stock prices via yfinance."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_us")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            count = await fetch_us_prices(db)
            await finish_step(db, step, success=True, metadata={"inserted": count})
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_prices_us failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 3: Instrument job_fetch_prices_crypto**

```python
async def job_fetch_prices_crypto(ctx: dict) -> dict:
    """ARQ job: fetch crypto prices via CoinGecko."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_crypto")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            count = await fetch_crypto_prices(db)
            await finish_step(db, step, success=True, metadata={"inserted": count})
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_prices_crypto failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 4: Instrument job_fetch_price_gold**

```python
async def job_fetch_price_gold(ctx: dict) -> dict:
    """ARQ job: fetch gold spot price."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_gold")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            count = await fetch_gold_price(db)
            await finish_step(db, step, success=True, metadata={"inserted": count})
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_price_gold failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 5: Instrument job_fetch_benchmark_prices**

```python
async def job_fetch_benchmark_prices(ctx: dict) -> dict:
    """ARQ job: fetch S&P500 and SET benchmark prices."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_benchmark")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            count = await fetch_benchmark_prices(db)
            await finish_step(db, step, success=True, metadata={"inserted": count})
            await finish_log(db, log, success=True)
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_benchmark_prices failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 6: Verify import compiles**

```bash
docker compose exec backend python -c "from worker.jobs.price_fetch import job_fetch_prices_us; print('OK')"
```

Expected: `OK`

---

## Task 6: Instrument watchlist_discover worker

**Files:**
- Modify: `backend/worker/jobs/watchlist_discover.py`

- [ ] **Step 1: Update imports**

Change:

```python
from app.services.pipeline import create_log, finish_log
```

To:

```python
from app.services.pipeline import create_log, finish_log, create_step, finish_step
```

- [ ] **Step 2: Replace job_discover_watchlist body**

```python
async def job_discover_watchlist(ctx: dict, user_id: str) -> dict:
    """ARQ job: ask LLM to suggest new tickers based on portfolio, save as WatchlistSuggestion rows."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "watchlist_discovery")
        try:
            user = (await db.execute(select(User).where(User.id == uuid.UUID(user_id)))).scalar_one_or_none()
            if not user:
                raise ValueError(f"User {user_id} not found")

            # Step 1: load_portfolio
            step_load = await create_step(db, log.id, "load_portfolio")
            holdings_rows = (await db.execute(
                select(Holding, Asset)
                .join(Asset, Holding.asset_id == Asset.id)
                .where(Holding.user_id == user.id)
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
            await finish_step(db, step_load, success=True, metadata={
                "holdings": len(holdings_rows),
                "watchlist": len(watchlist_rows),
            })

            # Step 2: llm_call
            step_llm = await create_step(db, log.id, "llm_call")
            gateway = LLMGateway(db)
            llm_result = await gateway.complete(
                "watchlist_discovery",
                user.id,
                {"holdings_txt": holdings_txt, "watchlist_txt": watchlist_txt},
            )
            logger.info("LLM watchlist_discovery response received, length=%d", len(llm_result.content))
            await finish_step(db, step_llm, success=True, metadata={
                "tokens_in": llm_result.tokens_in,
                "tokens_out": llm_result.tokens_out,
                "cost_usd": llm_result.cost_usd,
                "cost_thb": llm_result.cost_thb,
                "exchange_rate": llm_result.exchange_rate,
                "model": llm_result.model,
                "provider": llm_result.provider,
                "prompt": llm_result.prompt,
                "response": llm_result.content,
            })

            parsed = _parse_discovery_response(llm_result.content)
            if parsed is None:
                raise ValueError(f"LLM returned malformed JSON: {llm_result.content[:200]}")

            # Step 3: save_suggestions
            step_save = await create_step(db, log.id, "save_suggestions")
            saved = 0
            skipped = 0
            for item in parsed:
                sym = item["symbol"].upper()
                if sym in portfolio_symbols or sym in watchlist_symbols or sym in pending_symbols:
                    logger.debug("Skipping duplicate symbol: %s", sym)
                    skipped += 1
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
            await finish_step(db, step_save, success=True, metadata={"saved": saved, "skipped": skipped})
            await finish_log(db, log, success=True)
            logger.info("watchlist_discover done: %d suggestions saved", saved)
            return {"suggestions_saved": saved}
        except Exception as e:
            logger.exception("job_discover_watchlist failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 3: Verify import compiles**

```bash
docker compose exec backend python -c "from worker.jobs.watchlist_discover import job_discover_watchlist; print('OK')"
```

Expected: `OK`

---

## Task 7: Instrument watchlist_scan worker

**Files:**
- Modify: `backend/worker/jobs/watchlist_scan.py`

- [ ] **Step 1: Update imports**

Change:

```python
from app.services.pipeline import create_log, finish_log
```

To:

```python
from app.services.pipeline import create_log, finish_log, create_step, finish_step
```

- [ ] **Step 2: Replace job_scan_watchlist_item body**

```python
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

            # Step 1: load_asset
            step_load = await create_step(db, log.id, "load_asset")
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
            await finish_step(db, step_load, success=True, metadata={"symbol": asset.symbol, "price_days": len(prices)})

            # Step 2: rag_retrieval
            step_rag = await create_step(db, log.id, "rag_retrieval")
            collection = get_or_create_collection(asset.symbol)
            rag_chunks = search(collection, query=f"{asset.symbol} financial analysis outlook")
            rag_context = "\n\n---\n\n".join(rag_chunks) if rag_chunks else "No research documents available."
            await finish_step(db, step_rag, success=True, metadata={"chunks_found": len(rag_chunks)})

            # Step 3: llm_call
            step_llm = await create_step(db, log.id, "llm_call")
            gateway = LLMGateway(db)
            llm_result = await gateway.complete(
                "watchlist_scan",
                uuid.UUID(user_id),
                {"symbol": asset.symbol, "prices_txt": prices_txt, "rag_context": rag_context},
            )
            parsed = _parse_scan_response(llm_result.content)
            if parsed is None:
                raise ValueError(f"LLM returned malformed JSON: {llm_result.content[:200]}")
            await finish_step(db, step_llm, success=True, metadata={
                "tokens_in": llm_result.tokens_in,
                "tokens_out": llm_result.tokens_out,
                "cost_usd": llm_result.cost_usd,
                "cost_thb": llm_result.cost_thb,
                "exchange_rate": llm_result.exchange_rate,
                "model": llm_result.model,
                "provider": llm_result.provider,
                "prompt": llm_result.prompt,
                "response": llm_result.content,
            })

            # Step 4: save_suggestion
            step_save = await create_step(db, log.id, "save_suggestion")
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
            await finish_step(db, step_save, success=True, metadata={"symbol": asset.symbol, "verdict": parsed["verdict"]})
            await finish_log(db, log, success=True)
            logger.info("watchlist_scan done item=%s verdict=%s", item_id, parsed["verdict"])
            return {"verdict": parsed["verdict"], "analysis_id": str(analysis.id)}
        except Exception as e:
            logger.exception("job_scan_watchlist_item failed item=%s: %s", item_id, e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 3: Verify import compiles**

```bash
docker compose exec backend python -c "from worker.jobs.watchlist_scan import job_scan_watchlist_item; print('OK')"
```

Expected: `OK`

---

## Task 8: Instrument run_analysis worker

**Files:**
- Modify: `backend/worker/jobs/run_analysis.py`

- [ ] **Step 1: Update imports**

Change:

```python
from app.services.pipeline import create_log, finish_log
```

To:

```python
from app.services.pipeline import create_log, finish_log, create_step, finish_step
```

- [ ] **Step 2: Replace job_run_analysis body**

```python
async def job_run_analysis(ctx: dict, symbol: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "run_analysis")
        try:
            from app.models.asset import Asset
            from app.models.holding import Holding
            from app.models.price import Price

            # Step 1: load_asset
            step_load = await create_step(db, log.id, "load_asset")
            a_result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
            asset = a_result.scalar_one_or_none()
            if not asset:
                raise ValueError(f"Asset {symbol} not found")

            h_result = await db.execute(select(Holding).where(Holding.asset_id == asset.id))
            holdings = h_result.scalars().all()

            since = datetime.now(timezone.utc) - timedelta(days=90)
            p_result = await db.execute(
                select(Price)
                .where(Price.asset_id == asset.id, Price.timestamp >= since)
                .order_by(desc(Price.timestamp))
                .limit(90)
            )
            prices = p_result.scalars().all()
            await finish_step(db, step_load, success=True, metadata={
                "symbol": symbol.upper(),
                "holdings": len(holdings),
                "price_days": len(prices),
            })

            # Step 2: rag_retrieval
            step_rag = await create_step(db, log.id, "rag_retrieval")
            collection = get_or_create_collection(symbol)
            rag_chunks = search(collection, query=f"{symbol} financial analysis earnings revenue")
            rag_context = "\n\n---\n\n".join(rag_chunks) if rag_chunks else "No documents available."
            await finish_step(db, step_rag, success=True, metadata={"chunks_found": len(rag_chunks)})

            holdings_txt = "\n".join(
                f"- {h.quantity} units @ avg cost {h.avg_cost}" for h in holdings
            ) or "No current holdings."
            prices_txt = "\n".join(
                f"{p.timestamp.date()}: close={p.close}" for p in prices[:10]
            ) if prices else "No price history."

            user_prompt = f"""Asset: {symbol}

Holdings:
{holdings_txt}

Recent price history (last 10 days):
{prices_txt}

Research documents context:
{rag_context}

Provide your BUY/SELL/HOLD verdict as JSON."""

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            # Step 3: llm_call
            step_llm = await create_step(db, log.id, "llm_call")
            llm = await get_llm_provider(db)
            resp = await llm.complete(messages)
            parsed = _parse_verdict(resp.content)

            if parsed is None:
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": FORMAT_REMINDER})
                resp2 = await llm.complete(messages)
                parsed = _parse_verdict(resp2.content)
                if parsed is None:
                    raise ValueError(f"LLM returned malformed JSON after retry: {resp2.content[:200]}")
                resp = resp2

            usd_thb = await get_current_usd_thb(db)
            cost_thb = float(resp.cost_usd) * float(usd_thb) if usd_thb else 0.0
            await finish_step(db, step_llm, success=True, metadata={
                "tokens_in": resp.tokens_in,
                "tokens_out": resp.tokens_out,
                "cost_usd": float(resp.cost_usd),
                "cost_thb": cost_thb,
                "exchange_rate": float(usd_thb) if usd_thb else 0.0,
                "model": getattr(llm, "model", "unknown"),
                "provider": type(llm).__name__.replace("Provider", "").lower(),
                "prompt": user_prompt,
                "response": resp.content,
            })

            # Step 4: save_analysis
            step_save = await create_step(db, log.id, "save_analysis")
            analysis = AIAnalysis(
                asset_id=asset.id,
                job_id=str(log.id),
                verdict=parsed["verdict"],
                target_price=parsed.get("target_price"),
                reasoning=parsed["reasoning"],
                provider=type(llm).__name__.replace("Provider", "").lower(),
                model=getattr(llm, "model", "unknown"),
                tokens_in=resp.tokens_in,
                tokens_out=resp.tokens_out,
                cost_usd=resp.cost_usd,
            )
            db.add(analysis)
            await db.flush()

            for i, msg in enumerate(messages + [{"role": "assistant", "content": resp.content}]):
                db.add(LLMConversation(
                    analysis_id=analysis.id,
                    role=msg["role"],
                    content=msg["content"],
                    message_order=i,
                ))

            await db.commit()
            await finish_step(db, step_save, success=True, metadata={
                "verdict": parsed["verdict"],
                "analysis_id": str(analysis.id),
            })
            await finish_log(db, log, success=True)
            logger.info("run_analysis done symbol=%s verdict=%s", symbol, parsed["verdict"])
            return {"verdict": parsed["verdict"], "analysis_id": str(analysis.id)}
        except Exception as e:
            logger.exception("run_analysis failed symbol=%s: %s", symbol, e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

Also add the missing import to `run_analysis.py`:

```python
from app.services.exchange_rate import get_current_usd_thb
```

- [ ] **Step 3: Verify import compiles**

```bash
docker compose exec backend python -c "from worker.jobs.run_analysis import job_run_analysis; print('OK')"
```

Expected: `OK`

---

## Task 9: Instrument ingest_document worker

**Files:**
- Modify: `backend/worker/jobs/ingest_document.py`

- [ ] **Step 1: Update imports**

Change:

```python
from app.services.pipeline import create_log, finish_log
```

To:

```python
from app.services.pipeline import create_log, finish_log, create_step, finish_step
```

- [ ] **Step 2: Replace job_ingest_document body**

```python
async def job_ingest_document(ctx: dict, document_id: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "ingest_document")
        doc_uuid = uuid.UUID(document_id)
        result = await db.execute(select(Document).where(Document.id == doc_uuid))
        doc = result.scalar_one_or_none()
        if not doc:
            await finish_log(db, log, success=False, error_message=f"Document {document_id} not found")
            return {"error": "not found"}
        try:
            doc.status = "processing"
            await db.commit()

            # Step 1: load_document
            step_load = await create_step(db, log.id, "load_document")
            import fitz
            import os
            pdf = fitz.open(doc.file_path)
            full_text = "\n".join(page.get_text() for page in pdf)
            pdf.close()
            file_size = os.path.getsize(doc.file_path) if os.path.exists(doc.file_path) else 0
            await finish_step(db, step_load, success=True, metadata={
                "filename": doc.file_path.split("/")[-1],
                "size_bytes": file_size,
            })

            # Step 2: chunk_text
            step_chunk = await create_step(db, log.id, "chunk_text")
            chunks = _recursive_chunk(full_text)
            await finish_step(db, step_chunk, success=True, metadata={"chunks": len(chunks)})

            asset_symbol = None
            if doc.asset_id:
                from app.models.asset import Asset
                a_result = await db.execute(select(Asset).where(Asset.id == doc.asset_id))
                asset = a_result.scalar_one_or_none()
                asset_symbol = asset.symbol if asset else None

            # Step 3: embed_store
            step_embed = await create_step(db, log.id, "embed_store")
            collection = get_or_create_collection(asset_symbol)
            metadatas = [
                {"document_id": document_id, "chunk_index": i, "asset_symbol": asset_symbol or "global"}
                for i in range(len(chunks))
            ]
            ids = [f"{document_id}_{i}" for i in range(len(chunks))]
            add_chunks(collection, chunks, metadatas, ids)
            await finish_step(db, step_embed, success=True, metadata={"embedded": len(chunks)})

            doc.status = "done"
            doc.chunk_count = len(chunks)
            doc.chroma_collection_id = collection.name
            await db.commit()

            await finish_log(db, log, success=True)
            logger.info("ingest_document done id=%s chunks=%d", document_id, len(chunks))
            return {"chunks": len(chunks)}
        except Exception as e:
            logger.exception("ingest_document failed id=%s: %s", document_id, e)
            doc.status = "failed"
            doc.error_msg = str(e)
            await db.commit()
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 3: Verify import compiles**

```bash
docker compose exec backend python -c "from worker.jobs.ingest_document import job_ingest_document; print('OK')"
```

Expected: `OK`

---

## Task 10: Frontend types

**Files:**
- Modify: `frontend/lib/services/pipeline.ts`

- [ ] **Step 1: Replace pipeline.ts**

```typescript
import { api } from "@/lib/api";

export type JobType =
  | "price_fetch_us"
  | "price_fetch_crypto"
  | "price_fetch_gold"
  | "price_fetch_benchmark"
  | "watchlist_discovery"
  | "watchlist_scan"
  | "run_analysis"
  | "ingest_document";

export type JobStatus = "queued" | "running" | "done" | "failed";
export type StepStatus = "running" | "done" | "failed";

export interface PipelineStep {
  id: string;
  pipeline_log_id: string;
  step_name: string;
  status: StepStatus;
  started_at: string;
  finished_at: string | null;
  metadata: Record<string, unknown> | null;
  error_message: string | null;
}

export interface PipelineJob {
  id: string;
  job_type: JobType;
  status: JobStatus;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
  steps: PipelineStep[];
}

export async function fetchJobs(limit = 50): Promise<PipelineJob[]> {
  const res = await api.get(`/api/v1/pipeline/jobs?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch pipeline jobs");
  return res.json();
}

export async function triggerJob(
  job_type: JobType,
): Promise<{ enqueued: boolean; job_id: string | null }> {
  const res = await api.post(`/api/v1/pipeline/trigger/${job_type}`, {});
  if (!res.ok) throw new Error("Failed to trigger job");
  return res.json();
}
```

---

## Task 11: StepList component

**Files:**
- Create: `frontend/components/pipeline/StepList.tsx`

- [ ] **Step 1: Create StepList.tsx**

```tsx
"use client";

import { useState } from "react";
import { type PipelineStep } from "@/lib/services/pipeline";

const STEP_LABELS: Record<string, string> = {
  fetch_and_store: "Fetch & Store",
  load_portfolio: "Load Portfolio",
  llm_call: "LLM Call",
  save_suggestions: "Save Suggestions",
  load_asset: "Load Asset",
  rag_retrieval: "RAG Retrieval",
  save_analysis: "Save Analysis",
  save_suggestion: "Save Suggestion",
  load_document: "Load Document",
  chunk_text: "Chunk Text",
  embed_store: "Embed & Store",
};

function stepDuration(step: PipelineStep): string {
  if (!step.finished_at) return "running…";
  const ms =
    new Date(step.finished_at).getTime() - new Date(step.started_at).getTime();
  return `${(ms / 1000).toFixed(1)}s`;
}

function StepIcon({ status }: { status: string }) {
  if (status === "done") return <span className="text-green-600 text-xs">✓</span>;
  if (status === "failed") return <span className="text-destructive text-xs">✗</span>;
  return <span className="text-blue-500 text-xs animate-pulse">●</span>;
}

function LLMMetadata({ m }: { m: Record<string, unknown> }) {
  const [showPrompt, setShowPrompt] = useState(false);
  const [showResponse, setShowResponse] = useState(false);

  return (
    <div className="space-y-1 ml-5">
      <div className="flex gap-3 text-xs text-muted-foreground flex-wrap">
        <span>↑{String(m.tokens_in)} / ↓{String(m.tokens_out)}</span>
        <span>${Number(m.cost_usd).toFixed(6)}</span>
        <span>฿{Number(m.cost_thb).toFixed(4)}</span>
        <span className="text-muted-foreground/60">
          {String(m.model)} · {String(m.provider)}
        </span>
      </div>
      <div className="flex gap-3">
        <button
          className="text-xs text-blue-500 underline underline-offset-2"
          onClick={() => setShowPrompt((v) => !v)}
        >
          Prompt {showPrompt ? "▴" : "▾"}
        </button>
        <button
          className="text-xs text-blue-500 underline underline-offset-2"
          onClick={() => setShowResponse((v) => !v)}
        >
          Response {showResponse ? "▴" : "▾"}
        </button>
      </div>
      {showPrompt && (
        <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-48 whitespace-pre-wrap font-mono">
          {String(m.prompt)}
        </pre>
      )}
      {showResponse && (
        <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-48 whitespace-pre-wrap font-mono">
          {String(m.response)}
        </pre>
      )}
    </div>
  );
}

function GenericMetadata({ m }: { m: Record<string, unknown> }) {
  const entries = Object.entries(m);
  if (entries.length === 0) return null;
  return (
    <p className="ml-5 text-xs text-muted-foreground">
      {entries.map(([k, v]) => `${k}: ${v}`).join(" · ")}
    </p>
  );
}

interface StepListProps {
  steps: PipelineStep[];
}

export function StepList({ steps }: StepListProps) {
  if (steps.length === 0) {
    return (
      <p className="text-xs text-muted-foreground py-2 ml-4">
        No step data recorded.
      </p>
    );
  }

  return (
    <div className="ml-4 border-l pl-4 py-2 space-y-2">
      {steps.map((step) => (
        <div key={step.id} className="space-y-1">
          <div className="flex items-center gap-2 text-sm">
            <StepIcon status={step.status} />
            <span className="font-medium">
              {STEP_LABELS[step.step_name] ?? step.step_name}
            </span>
            <span className="text-muted-foreground text-xs">
              {stepDuration(step)}
            </span>
          </div>
          {step.metadata &&
            (step.step_name === "llm_call" ? (
              <LLMMetadata m={step.metadata as Record<string, unknown>} />
            ) : (
              <GenericMetadata m={step.metadata as Record<string, unknown>} />
            ))}
          {step.error_message && (
            <p className="ml-5 text-xs text-destructive font-mono">
              {step.error_message}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
```

---

## Task 12: JobsTable expandable rows

**Files:**
- Modify: `frontend/components/pipeline/JobsTable.tsx`

- [ ] **Step 1: Replace JobsTable.tsx**

```tsx
"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type PipelineJob,
  type JobType,
  triggerJob,
} from "@/lib/services/pipeline";
import { StepList } from "@/components/pipeline/StepList";
import { toast } from "sonner";

const STATUS_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  done: "default",
  running: "secondary",
  queued: "outline",
  failed: "destructive",
};

const JOB_LABELS: Record<JobType, string> = {
  price_fetch_us: "US Stocks",
  price_fetch_crypto: "Crypto",
  price_fetch_gold: "Gold",
  price_fetch_benchmark: "Benchmarks",
  watchlist_discovery: "Watchlist Discovery",
  watchlist_scan: "Watchlist Scan",
  run_analysis: "AI Analysis",
  ingest_document: "Ingest Document",
};

const ALL_TRIGGER_TYPES: JobType[] = [
  "price_fetch_us",
  "price_fetch_crypto",
  "price_fetch_gold",
  "price_fetch_benchmark",
];

interface JobsTableProps {
  jobs: PipelineJob[];
}

export function JobsTable({ jobs }: JobsTableProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  function toggleExpand(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleTrigger(jobType: JobType) {
    try {
      await triggerJob(jobType);
      toast.success(`${JOB_LABELS[jobType]} job enqueued`);
    } catch {
      toast.error(`Failed to trigger ${JOB_LABELS[jobType]} job`);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Pipeline Jobs</CardTitle>
        <div className="flex gap-2 flex-wrap">
          {ALL_TRIGGER_TYPES.map((jt) => (
            <Button
              key={jt}
              size="sm"
              variant="outline"
              onClick={() => handleTrigger(jt)}
            >
              Run {JOB_LABELS[jt]}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-muted-foreground">
              <th className="text-left py-2 pr-4 w-4"></th>
              <th className="text-left py-2 pr-4">Job</th>
              <th className="text-left py-2 pr-4">Status</th>
              <th className="text-left py-2 pr-4">Started</th>
              <th className="text-left py-2">Duration</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="py-8 text-center text-muted-foreground"
                >
                  No jobs have run yet. Use the buttons above to trigger a fetch.
                </td>
              </tr>
            )}
            {jobs.map((job) => {
              const duration =
                job.finished_at && job.started_at
                  ? `${((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000).toFixed(1)}s`
                  : job.status === "running"
                    ? "running…"
                    : "—";
              const isExpanded = expandedIds.has(job.id);

              return (
                <>
                  <tr
                    key={job.id}
                    className="border-b cursor-pointer hover:bg-muted/40 transition-colors"
                    onClick={() => toggleExpand(job.id)}
                  >
                    <td className="py-2 pr-2 text-muted-foreground text-xs">
                      {isExpanded ? "▴" : "▾"}
                    </td>
                    <td className="py-2 pr-4 font-medium">
                      {JOB_LABELS[job.job_type as JobType] ?? job.job_type}
                    </td>
                    <td className="py-2 pr-4">
                      <Badge variant={STATUS_VARIANT[job.status] ?? "outline"}>
                        {job.status}
                      </Badge>
                    </td>
                    <td className="py-2 pr-4 text-muted-foreground">
                      {new Date(job.started_at).toLocaleString()}
                    </td>
                    <td className="py-2 text-muted-foreground">{duration}</td>
                  </tr>
                  {isExpanded && (
                    <tr key={`${job.id}-steps`} className="border-b bg-muted/20">
                      <td colSpan={5} className="py-2 px-2">
                        <StepList steps={job.steps ?? []} />
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
        {jobs.some((j) => j.status === "failed") && (
          <div className="mt-4 space-y-2">
            {jobs
              .filter((j) => j.status === "failed" && j.error_message)
              .map((j) => (
                <p
                  key={j.id}
                  className="text-xs text-destructive font-mono bg-destructive/10 p-2 rounded"
                >
                  [{JOB_LABELS[j.job_type as JobType]}] {j.error_message}
                </p>
              ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /path/to/frontend && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Smoke test in browser**

Start dev server, open Pipeline Monitor page, click a job row. Verify:
- Row expands/collapses on click
- Steps appear with name, status icon, duration
- LLM jobs show token/cost chips and Prompt/Response toggles
- Running steps show pulsing dot and "running…"
- SSE updates cause step list to refresh live
