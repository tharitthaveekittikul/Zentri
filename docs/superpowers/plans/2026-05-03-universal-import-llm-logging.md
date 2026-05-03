# Universal Import + LLM Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a canonical transaction schema that all broker imports normalize to, and upgrade the LLM gateway to automatically log every call with full token and cost data.

**Architecture:** A new `canonical.py` module defines the fixed output schema and `apply_template` logic (with value transforms, derived fields, and defaults). The `LLMGateway` is upgraded so all adapters return `LLMResponse` with token counts, and every call is auto-logged to a new `llm_call_logs` table. A new `exchange_rate` service fetches and caches historical USD/THB rates for trade-date accuracy.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, TimescaleDB (PostgreSQL), httpx, pytest, pytest-asyncio, Next.js 15, TypeScript

---

## File Map

### New Files

| File                                                           | Responsibility                                                                       |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `backend/app/core/canonical.py`                                | `CANONICAL_FIELDS`, `apply_template`, `_eval_expression`, `_classify_row_asset_type` |
| `backend/app/models/llm_call_log.py`                           | `LLMCallLog` SQLAlchemy model                                                        |
| `backend/app/models/exchange_rate_cache.py`                    | `ExchangeRateCache` SQLAlchemy model                                                 |
| `backend/app/services/exchange_rate.py`                        | Fetch + cache historical/current USD/THB rates                                       |
| `backend/app/api/llm_usage.py`                                 | `GET /llm/call-logs` endpoint                                                        |
| `backend/alembic/versions/006_universal_import_llm_logging.py` | All DB changes for this feature                                                      |
| `backend/tests/core/test_canonical.py`                         | Unit tests for canonical module                                                      |
| `backend/tests/services/test_exchange_rate.py`                 | Tests for exchange rate service                                                      |
| `backend/tests/conftest.py`                                    | Shared pytest fixtures                                                               |

### Modified Files

| File                                       | Change                                                                                       |
| ------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `backend/app/services/llm_service.py`      | Rename `_calc_cost` → `calc_cost`, add Gemini models to PRICING, fix Gemini token extraction |
| `backend/app/services/llm_gateway.py`      | All adapters return `LLMResponse`; `complete()` auto-logs to `llm_call_logs`                 |
| `backend/app/services/import_pipeline.py`  | Update LLM prompts, use `canonical.apply_template`, add exchange rate enrichment             |
| `backend/app/models/import_template.py`    | Add `value_transforms`, `derived_fields`, `defaults` JSONB columns                           |
| `backend/app/models/user.py`               | Add `currency_primary`, `currency_secondary`                                                 |
| `backend/app/schemas/import_template.py`   | Expose new template fields                                                                   |
| `backend/app/api/import_pipeline.py`       | Add `DELETE /import/template/{platform_id}` re-map endpoint                                  |
| `backend/app/api/settings.py`              | Add `GET /settings/display` and `PATCH /settings/display` endpoints                          |
| `backend/app/main.py`                      | Register `llm_usage` router                                                                  |
| `frontend/app/(auth)/settings/ai/page.tsx` | Add tabs + summary cards to AI Usage page                                                    |
| `frontend/app/(auth)/import/page.tsx`      | Add Re-map button                                                                            |
| `frontend/app/(auth)/settings/page.tsx`    | Add currency display preference section                                                      |

---

## Task 1: Canonical Schema Module

**Files:**

- Create: `backend/app/core/canonical.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/core/test_canonical.py`

- [ ] **Step 1: Create test directory structure**

```bash
mkdir -p backend/tests/core backend/tests/services
touch backend/tests/__init__.py backend/tests/core/__init__.py backend/tests/services/__init__.py
```

- [ ] **Step 2: Create `backend/tests/conftest.py`**

```python
import pytest

@pytest.fixture
def sample_finnomena_rows():
    return [
        {"Template": "Buy Note", "Fund_Code": "SCBSET50", "Trade_Date": "2026-04-27",
         "Total_Amount": "500", "Number_of_Units": "22.5926", "Filename": "confirmation.pdf"},
    ]

@pytest.fixture
def sample_dime_rows():
    return [
        {"type": "BUY", "symbol": "ABNB", "unit": "0.2889284", "price": "95.56",
         "currency": "USD", "settlement_date": "28/11/2022", "gross_ccy": "27.61",
         "fee_ccy": "0.00", "exchange_rate": "35.9775", "total_buy_thb": "993.34"},
    ]

@pytest.fixture
def sample_streaming_rows():
    return [
        {"type": "BUY", "share_name": "PTT", "unit": 100, "unit_price": 34.5,
         "net_amount": 3455.8, "trading_date": "30/09/2022"},
    ]
```

- [ ] **Step 3: Write failing tests for `apply_template`**

```python
# backend/tests/core/test_canonical.py
from decimal import Decimal
import pytest
from app.core.canonical import apply_template, CANONICAL_FIELDS


def test_canonical_fields_list():
    assert "trade_date" in CANONICAL_FIELDS
    assert "type" in CANONICAL_FIELDS
    assert "symbol" in CANONICAL_FIELDS
    assert "unit" in CANONICAL_FIELDS
    assert "gross_thb" in CANONICAL_FIELDS
    assert "exchange_rate" in CANONICAL_FIELDS


def test_apply_template_direct_mapping(sample_finnomena_rows):
    template = {
        "field_map": {
            "Fund_Code": "symbol",
            "Trade_Date": "trade_date",
            "Number_of_Units": "unit",
            "Total_Amount": "gross_thb",
        },
        "value_transforms": {},
        "derived_fields": {},
        "defaults": {"currency": "THB"},
        "asset_type_rules": [],
        "asset_type_fallback": "th_fund",
    }
    result = apply_template(sample_finnomena_rows, template)
    assert result[0]["symbol"] == "SCBSET50"
    assert result[0]["currency"] == "THB"
    assert result[0]["asset_type"] == "th_fund"


def test_apply_template_value_transforms(sample_finnomena_rows):
    template = {
        "field_map": {"Template": "type", "Fund_Code": "symbol",
                      "Total_Amount": "gross_thb", "Number_of_Units": "unit"},
        "value_transforms": {"type": {"Buy Note": "BUY", "Sell Note": "SELL", "Manual": "BUY"}},
        "derived_fields": {},
        "defaults": {"currency": "THB"},
        "asset_type_rules": [],
        "asset_type_fallback": "th_fund",
    }
    result = apply_template(sample_finnomena_rows, template)
    assert result[0]["type"] == "BUY"


def test_apply_template_derived_fields(sample_finnomena_rows):
    template = {
        "field_map": {"Total_Amount": "gross_thb", "Number_of_Units": "unit"},
        "value_transforms": {},
        "derived_fields": {"price": "gross_thb / unit"},
        "defaults": {"currency": "THB"},
        "asset_type_rules": [],
        "asset_type_fallback": "th_fund",
    }
    result = apply_template(sample_finnomena_rows, template)
    price = result[0]["price"]
    assert price is not None
    assert abs(float(price) - (500 / 22.5926)) < 0.01


def test_apply_template_derived_null_when_missing():
    rows = [{"gross_thb": "100"}]
    template = {
        "field_map": {},
        "value_transforms": {},
        "derived_fields": {"price": "gross_thb / unit"},
        "defaults": {},
        "asset_type_rules": [],
        "asset_type_fallback": "us_stock",
    }
    result = apply_template(rows, template)
    assert result[0]["price"] is None


def test_apply_template_defaults_fill_nulls():
    rows = [{"symbol": "PTT", "unit": "100"}]
    template = {
        "field_map": {},
        "value_transforms": {},
        "derived_fields": {},
        "defaults": {"currency": "THB", "exchange": "SET"},
        "asset_type_rules": [],
        "asset_type_fallback": "thai_stock",
    }
    result = apply_template(rows, template)
    assert result[0]["currency"] == "THB"
    assert result[0]["exchange"] == "SET"
```

- [ ] **Step 4: Run tests — expect FAIL (module not found)**

```bash
cd backend && python -m pytest tests/core/test_canonical.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'app.core.canonical'`

- [ ] **Step 5: Create `backend/app/core/canonical.py`**

```python
from __future__ import annotations

import operator as _op
import re
from decimal import Decimal, InvalidOperation
from typing import Any

CANONICAL_FIELDS = [
    "trade_date", "type", "symbol", "unit", "price", "currency",
    "exchange", "gross_amount", "fee", "gross_thb", "fee_thb",
    "exchange_rate", "asset_type", "platform", "notes",
]

CANONICAL_TYPES = frozenset(["BUY", "SELL", "DIVIDEND", "REWARD", "FEE", "TRANSFER"])
CANONICAL_ASSET_TYPES = frozenset(
    ["us_stock", "thai_stock", "th_fund", "etf", "crypto", "gold", "cash"]
)

_OPERATORS = {"/": _op.truediv, "*": _op.mul, "+": _op.add, "-": _op.sub}


def _eval_expression(expr: str, row: dict[str, Any]) -> Decimal | None:
    expr = expr.strip()
    for op_char, op_fn in _OPERATORS.items():
        if op_char in expr:
            left_key, right_key = expr.split(op_char, 1)
            left_val = row.get(left_key.strip())
            right_val = row.get(right_key.strip())
            if left_val is None or right_val is None:
                return None
            try:
                l, r = Decimal(str(left_val)), Decimal(str(right_val))
                if op_char == "/" and r == 0:
                    return None
                return op_fn(l, r)
            except (InvalidOperation, ZeroDivisionError):
                return None
    val = row.get(expr)
    return Decimal(str(val)) if val is not None else None


def _classify_row_asset_type(row: dict, rules: list[dict], fallback: str) -> str:
    for rule in rules:
        field = rule.get("field", "")
        value = str(row.get(field, ""))
        if "values" in rule:
            if value in rule["values"]:
                return rule["asset_type"]
        elif "pattern" in rule:
            if re.match(rule["pattern"], value, re.IGNORECASE):
                return rule["asset_type"]
    return fallback


def apply_template(rows: list[dict], template: dict) -> list[dict]:
    field_map: dict[str, str] = template.get("field_map", {})
    value_transforms: dict[str, dict] = template.get("value_transforms", {})
    derived_fields: dict[str, str] = template.get("derived_fields", {})
    defaults: dict[str, Any] = template.get("defaults", {})
    asset_type_rules: list[dict] = template.get("asset_type_rules", [])
    fallback: str = template.get("asset_type_fallback", "us_stock")

    result = []
    for raw in rows:
        normalized: dict[str, Any] = {}

        for k in CANONICAL_FIELDS:
            if k in raw:
                normalized[k] = raw[k]

        for src, dst in field_map.items():
            if src in raw:
                normalized[dst] = raw[src]

        for canonical_key, transform_map in value_transforms.items():
            if canonical_key in normalized:
                val = str(normalized[canonical_key])
                normalized[canonical_key] = transform_map.get(val, normalized[canonical_key])

        for dst_key, expr in derived_fields.items():
            if normalized.get(dst_key) is None:
                normalized[dst_key] = _eval_expression(expr, normalized)

        for k, v in defaults.items():
            if normalized.get(k) is None:
                normalized[k] = v

        normalized["asset_type"] = _classify_row_asset_type(raw, asset_type_rules, fallback)
        result.append(normalized)
    return result
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
cd backend && python -m pytest tests/core/test_canonical.py -v
```

Expected: All 6 tests pass.

---

## Task 2: New Database Models

**Files:**

- Create: `backend/app/models/llm_call_log.py`
- Create: `backend/app/models/exchange_rate_cache.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create `backend/app/models/llm_call_log.py`**

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    feature_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_in: Mapped[str] = mapped_column(Text, nullable=False)
    response_out: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    cost_thb: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
```

- [ ] **Step 2: Create `backend/app/models/exchange_rate_cache.py`**

```python
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExchangeRateCache(Base):
    __tablename__ = "exchange_rate_cache"
    __table_args__ = (UniqueConstraint("rate_date", "from_currency", "to_currency"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    from_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 3: Register models in `backend/app/models/__init__.py`**

Open the file and add imports so Alembic autogenerate detects them:

```python
from app.models.llm_call_log import LLMCallLog  # noqa: F401
from app.models.exchange_rate_cache import ExchangeRateCache  # noqa: F401
```

---

## Task 3: Extend ImportTemplate + User Currency Prefs + Migration

**Files:**

- Modify: `backend/app/models/import_template.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/schemas/import_template.py`
- Create: `backend/alembic/versions/006_universal_import_llm_logging.py`

- [ ] **Step 1: Add new columns to `ImportTemplate` model**

In `backend/app/models/import_template.py`, add three columns after `currency_default`:

```python
value_transforms: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
derived_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
defaults: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
```

- [ ] **Step 2: Add currency preferences to `User` model**

In `backend/app/models/user.py`, add after `created_at`:

```python
currency_primary: Mapped[str] = mapped_column(String(10), nullable=False, default="THB")
currency_secondary: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
```

- [ ] **Step 3: Update `ImportTemplateOut` schema**

In `backend/app/schemas/import_template.py`, add to `ImportTemplateOut`:

```python
value_transforms: dict
derived_fields: dict
defaults: dict
```

- [ ] **Step 4: Generate migration**

```bash
cd backend && alembic revision --autogenerate -m "universal_import_llm_logging"
```

Expected: Creates `backend/alembic/versions/006_universal_import_llm_logging.py`

- [ ] **Step 5: Verify migration content**

Open the generated migration. Verify `upgrade()` contains:

- `op.create_table("llm_call_logs", ...)`
- `op.create_table("exchange_rate_cache", ...)`
- `op.add_column("import_templates", sa.Column("value_transforms", ...))`
- `op.add_column("import_templates", sa.Column("derived_fields", ...))`
- `op.add_column("import_templates", sa.Column("defaults", ...))`
- `op.add_column("users", sa.Column("currency_primary", ...))`
- `op.add_column("users", sa.Column("currency_secondary", ...))`

If any are missing, add them manually. Then run:

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade ... -> 006_...`

---

## Task 4: Exchange Rate Service

**Files:**

- Create: `backend/app/services/exchange_rate.py`
- Create: `backend/tests/services/test_exchange_rate.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_exchange_rate.py
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from app.services.exchange_rate import get_historical_usd_thb, get_current_usd_thb


@pytest.mark.asyncio
async def test_get_historical_usd_thb_returns_rate():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"usd": {"thb": 35.9775}}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await get_historical_usd_thb(mock_db, date(2022, 11, 28))

    assert result == Decimal("35.9775")


@pytest.mark.asyncio
async def test_get_historical_usd_thb_uses_cache():
    mock_db = AsyncMock()
    cached_row = MagicMock()
    cached_row.rate = Decimal("36.0")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = cached_row
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await get_historical_usd_thb(mock_db, date(2022, 11, 28))

    assert result == Decimal("36.0")
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_historical_usd_thb_returns_none_on_api_failure():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await get_historical_usd_thb(mock_db, date(2022, 11, 28))

    assert result is None
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && python -m pytest tests/services/test_exchange_rate.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.services.exchange_rate'`

- [ ] **Step 3: Create `backend/app/services/exchange_rate.py`**

```python
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.exchange_rate_cache import ExchangeRateCache

logger = get_logger(__name__)

_API_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/v1/currencies/usd.min.json"


async def get_historical_usd_thb(db: AsyncSession, rate_date: date) -> Decimal | None:
    cached = await _get_cached_rate(db, rate_date)
    if cached is not None:
        return cached

    date_str = rate_date.strftime("%Y-%m-%d")
    url = _API_URL.format(date=date_str)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            raw_rate = data.get("usd", {}).get("thb")
            if raw_rate is None:
                logger.warning("exchange_rate: thb not in API response for %s", date_str)
                return None
            rate = Decimal(str(raw_rate))
            await _cache_rate(db, rate_date, rate)
            logger.info("exchange_rate: fetched USD/THB=%.4f for %s", float(rate), date_str)
            return rate
    except Exception as exc:
        logger.warning("exchange_rate: fetch failed for %s: %s", date_str, exc)
        return None


async def get_current_usd_thb(db: AsyncSession) -> Decimal | None:
    return await get_historical_usd_thb(db, datetime.now(timezone.utc).date())


async def _get_cached_rate(db: AsyncSession, rate_date: date) -> Decimal | None:
    result = await db.execute(
        select(ExchangeRateCache).where(
            ExchangeRateCache.rate_date == rate_date,
            ExchangeRateCache.from_currency == "USD",
            ExchangeRateCache.to_currency == "THB",
        )
    )
    row = result.scalar_one_or_none()
    return row.rate if row else None


async def _cache_rate(db: AsyncSession, rate_date: date, rate: Decimal) -> None:
    entry = ExchangeRateCache(
        rate_date=rate_date,
        from_currency="USD",
        to_currency="THB",
        rate=rate,
    )
    db.add(entry)
    await db.flush()
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && python -m pytest tests/services/test_exchange_rate.py -v
```

Expected: All 3 tests pass.

---

## Task 5: Fix LLM Service (Public `calc_cost` + Gemini Tokens)

**Files:**

- Modify: `backend/app/services/llm_service.py`

- [ ] **Step 1: Rename `_calc_cost` to `calc_cost` and add missing Gemini models**

In `backend/app/services/llm_service.py`, find `def _calc_cost` and make these changes:

```python
PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6":         (3.0,   15.0),
    "claude-opus-4-7":           (15.0,  75.0),
    "claude-haiku-4-5-20251001": (0.8,   4.0),
    "gpt-4o":                    (2.5,   10.0),
    "gpt-4o-mini":               (0.15,  0.6),
    "gemini-1.5-pro":            (1.25,  5.0),
    "gemini-1.5-flash":          (0.075, 0.3),
    "gemini-2.0-flash":          (0.1,   0.4),
    "gemini-2.5-flash-lite":     (0.0,   0.0),
}


def calc_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    if model not in PRICING:
        return 0.0
    in_rate, out_rate = PRICING[model]
    return (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000
```

- [ ] **Step 2: Fix Gemini token extraction in `GeminiProvider.complete`**

Find the `GeminiProvider.complete` method and replace the return block:

```python
    async def complete(self, messages: list[dict]) -> LLMResponse:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        prompt = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
        response = await model.generate_content_async(prompt)
        content = response.text
        tokens_in = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        tokens_out = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        cost_usd = calc_cost(self.model, tokens_in, tokens_out)
        logger.info("gemini complete model=%s tokens_in=%d tokens_out=%d cost_usd=%.6f",
                    self.model, tokens_in, tokens_out, cost_usd)
        return LLMResponse(content=content, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd)
```

- [ ] **Step 3: Update all internal callers of `_calc_cost` in `llm_service.py`**

Search the file for `_calc_cost` and replace all occurrences with `calc_cost`:

```bash
grep -n "_calc_cost" backend/app/services/llm_service.py
```

Replace each occurrence (in `OpenAIProvider`, `ClaudeProvider`, etc.).

- [ ] **Step 4: Verify no broken imports**

```bash
cd backend && python -c "from app.services.llm_service import calc_cost, LLMResponse; print('OK')"
```

Expected: `OK`

---

## Task 6: Upgrade LLM Gateway (Auto-log Every Call)

**Files:**

- Modify: `backend/app/services/llm_gateway.py`
- Create: `backend/tests/services/test_llm_gateway.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/services/test_llm_gateway.py
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from app.services.llm_service import LLMResponse


@pytest.mark.asyncio
async def test_gateway_complete_logs_call():
    from app.services.llm_gateway import LLMGateway

    mock_db = AsyncMock()

    feature_config = MagicMock()
    feature_config.provider_config_id = uuid.uuid4()
    feature_config.system_prompt = "You are a test assistant."
    feature_config.model = "gemini-2.5-flash-lite"

    provider_config = MagicMock()
    provider_config.provider = "gemini"
    provider_config.encrypted_api_key = None
    provider_config.host_url = None
    provider_config.is_connected = True

    feature_result = MagicMock()
    feature_result.scalar_one_or_none.return_value = feature_config
    provider_result = MagicMock()
    provider_result.scalar_one_or_none.return_value = provider_config
    mock_db.execute = AsyncMock(side_effect=[feature_result, provider_result])
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    fake_response = LLMResponse(content="answer", tokens_in=10, tokens_out=5, cost_usd=0.0)

    with patch("app.services.llm_gateway._build_adapter") as mock_build:
        mock_adapter = AsyncMock()
        mock_adapter.complete = AsyncMock(return_value=fake_response)
        mock_build.return_value = mock_adapter

        with patch("app.services.llm_gateway.get_current_usd_thb", return_value=Decimal("35.5")):
            gateway = LLMGateway(mock_db)
            result = await gateway.complete(
                "import_template_generator",
                uuid.uuid4(),
                {"file_format": "csv", "headers": "[]", "sample_rows": "[]"},
            )

    assert result == "answer"
    mock_db.add.assert_called_once()
    log_obj = mock_db.add.call_args[0][0]
    assert log_obj.tokens_in == 10
    assert log_obj.tokens_out == 5
    assert log_obj.feature_key == "import_template_generator"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd backend && python -m pytest tests/services/test_llm_gateway.py -v 2>&1 | head -30
```

Expected: `AssertionError` — `mock_db.add` not called (gateway currently returns str without logging).

- [ ] **Step 3: Update all adapters in `llm_gateway.py` to return `LLMResponse`**

Add import at top of `backend/app/services/llm_gateway.py`:

```python
from app.services.llm_service import LLMResponse, calc_cost
```

Update `LLMAdapter` abstract class:

```python
class LLMAdapter(ABC):
    @abstractmethod
    async def complete(self, system: str, human: str, model: str) -> LLMResponse: ...
```

Update `AnthropicAdapter.complete`:

```python
    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        msg = await self._client.messages.create(
            model=model, max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": human}],
        )
        tokens_in = msg.usage.input_tokens
        tokens_out = msg.usage.output_tokens
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=msg.content[0].text, tokens_in=tokens_in,
                           tokens_out=tokens_out, cost_usd=cost_usd)
```

Update `OpenAIAdapter.complete`:

```python
    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": human}],
        )
        tokens_in = resp.usage.prompt_tokens
        tokens_out = resp.usage.completion_tokens
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=resp.choices[0].message.content or "",
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd)
```

Update Gemini adapter (`complete` at line ~136, check exact class name in file):

```python
    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        import google.generativeai as genai
        genai.configure(api_key=self._api_key)
        combined = f"{system}\n\n{human}"
        genai_model = genai.GenerativeModel(model)
        response = await genai_model.generate_content_async(combined)
        tokens_in = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        tokens_out = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=response.text, tokens_in=tokens_in,
                           tokens_out=tokens_out, cost_usd=cost_usd)
```

Update `OllamaAdapter.complete`:

```python
    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._host_url}/api/chat",
                json={"model": model, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": human},
                ], "stream": False},
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
        tokens_in = data.get("prompt_eval_count", 0)
        tokens_out = data.get("eval_count", 0)
        return LLMResponse(content=data["message"]["content"],
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=0.0)
```

Update `OpenRouterAdapter.complete` (check exact implementation in file — adapt same pattern):

```python
    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": model, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": human},
                ]},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=data["choices"][0]["message"]["content"] or "",
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd)
```

- [ ] **Step 4: Update `LLMGateway.complete()` to auto-log**

Replace the `complete` method body in `LLMGateway`:

```python
    async def complete(self, feature_key: str, user_id: uuid.UUID, variables: dict) -> str:
        from app.models.llm_call_log import LLMCallLog
        from app.services.exchange_rate import get_current_usd_thb

        config = await self._get_feature_config(feature_key, user_id)
        provider = await self._get_provider(config.provider_config_id)
        api_key = decrypt(provider.encrypted_api_key) if provider.encrypted_api_key else None
        adapter = _build_adapter(provider.provider, api_key, provider.host_url)
        system = config.system_prompt or DEFAULT_SYSTEM_PROMPTS.get(feature_key, "")
        human = HUMAN_PROMPTS[feature_key].format(**variables)
        logger.info("LLM call: feature=%s provider=%s model=%s", feature_key, provider.provider, config.model)

        response: LLMResponse = await adapter.complete(system, human, config.model)

        usd_thb = await get_current_usd_thb(self._db)
        cost_thb = float(response.cost_usd) * float(usd_thb) if usd_thb else 0.0

        log = LLMCallLog(
            user_id=user_id,
            feature_key=feature_key,
            provider=provider.provider,
            model=config.model,
            prompt_in=f"SYSTEM: {system}\n\nHUMAN: {human}",
            response_out=response.content,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=response.cost_usd,
            cost_thb=cost_thb,
            exchange_rate=float(usd_thb) if usd_thb else 0.0,
        )
        self._db.add(log)
        await self._db.flush()

        logger.info("LLM logged: tokens_in=%d tokens_out=%d cost_usd=%.6f",
                    response.tokens_in, response.tokens_out, response.cost_usd)
        return response.content
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
cd backend && python -m pytest tests/services/test_llm_gateway.py -v
```

Expected: 1 test passes.

---

## Task 7: Update Import Pipeline Service

**Files:**

- Modify: `backend/app/services/import_pipeline.py`
- Modify: `backend/app/services/llm_gateway.py` (prompts section)

- [ ] **Step 1: Update system + human prompts in `llm_gateway.py`**

Find `DEFAULT_SYSTEM_PROMPTS` and update `import_template_generator`:

```python
"import_template_generator": (
    "You are a financial data normalization expert. Given a transaction file structure, "
    "produce a JSON mapping template that translates source fields to the canonical schema.\n\n"
    "Canonical fields: trade_date (datetime), type (BUY|SELL|DIVIDEND|REWARD|FEE|TRANSFER), "
    "symbol (ticker or fund code), unit (decimal), price (decimal|null), currency (ISO code, default THB), "
    "exchange (exchange name|null), gross_amount (decimal|null), fee (decimal|null), "
    "gross_thb (decimal|null), fee_thb (decimal|null), exchange_rate (decimal|null), "
    "asset_type (us_stock|thai_stock|th_fund|etf|crypto|gold|cash|null), platform (str|null), notes (str|null).\n\n"
    "Respond with valid JSON only. No explanation."
),
```

Find `HUMAN_PROMPTS` and update `import_template_generator`:

```python
"import_template_generator": (
    "File format: {file_format}\n"
    "Headers/keys: {headers}\n"
    "Sample rows (first 3):\n{sample_rows}\n\n"
    "Return a JSON object with exactly these keys:\n"
    "- file_format: 'csv' or 'json'\n"
    "- json_path: dotted path to transaction array (null for csv or top-level array)\n"
    "- field_map: {{source_field: canonical_field}} direct field name mapping\n"
    "- value_transforms: {{canonical_field: {{source_value: canonical_value}}}} e.g. {{\"type\": {{\"Buy Note\": \"BUY\"}}}}\n"
    "- derived_fields: {{canonical_field: 'left_field / right_field'}} arithmetic from other canonical fields\n"
    "- defaults: {{canonical_field: value}} fill when field is missing or null\n"
    "- asset_type_rules: [{{\"field\": \"...\", \"values\": [...], \"asset_type\": \"...\"}}]\n"
    "- asset_type_fallback: canonical asset_type string"
),
```

- [ ] **Step 2: Update `generate_template_via_llm` in `import_pipeline.py`**

Find the function and update the JSON parsing to extract new fields:

````python
async def generate_template_via_llm(
    db: AsyncSession,
    user_id: uuid.UUID,
    file_format: str,
    structure: dict,
) -> dict:
    gateway = LLMGateway(db)
    raw = await gateway.complete(
        "import_template_generator",
        user_id,
        {
            "file_format": file_format,
            "headers": json.dumps(structure["headers"]),
            "sample_rows": json.dumps(structure["sample_rows"], ensure_ascii=False, indent=2),
        },
    )
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    template_data = json.loads(raw)
    # Ensure all expected keys exist with defaults
    template_data.setdefault("value_transforms", {})
    template_data.setdefault("derived_fields", {})
    template_data.setdefault("defaults", {})
    template_data.setdefault("asset_type_rules", [])
    template_data.setdefault("asset_type_fallback", "us_stock")
    return template_data
````

- [ ] **Step 3: Update `save_template` to persist new fields**

Find `save_template` in `import_pipeline.py` and update the `existing` branch and new-template branch to include:

```python
# In existing template update block:
existing.value_transforms = template_data.get("value_transforms", {})
existing.derived_fields = template_data.get("derived_fields", {})
existing.defaults = template_data.get("defaults", {})

# In new template creation block:
value_transforms=template_data.get("value_transforms", {}),
derived_fields=template_data.get("derived_fields", {}),
defaults=template_data.get("defaults", {}),
```

- [ ] **Step 4: Replace `apply_template` in `import_pipeline.py` with canonical version**

At the top of `import_pipeline.py`, add:

```python
from app.core.canonical import apply_template, _classify_row_asset_type  # noqa: F401
```

Remove the old `apply_template` and `_classify_row_asset_type` function definitions from `import_pipeline.py` (they now live in `canonical.py`).

- [ ] **Step 5: Add exchange rate enrichment to `apply_template` call sites**

In `import_pipeline.py`, add a new async function that enriches canonical rows with historical exchange rates:

```python
async def enrich_exchange_rates(
    db: AsyncSession,
    rows: list[dict],
) -> list[dict]:
    from app.services.exchange_rate import get_historical_usd_thb
    from datetime import date as date_type
    import dateutil.parser as dp

    for row in rows:
        if row.get("exchange_rate") is not None:
            continue
        currency = row.get("currency", "THB")
        if currency == "THB":
            row["exchange_rate"] = 1.0
            continue
        trade_date_raw = row.get("trade_date")
        if not trade_date_raw:
            continue
        try:
            trade_dt = dp.parse(str(trade_date_raw)).date()
            rate = await get_historical_usd_thb(db, trade_dt)
            if rate is not None:
                row["exchange_rate"] = float(rate)
                if row.get("gross_amount") and not row.get("gross_thb"):
                    row["gross_thb"] = float(row["gross_amount"]) * float(rate)
        except Exception:
            pass
    return rows
```

- [ ] **Step 6: Wire `enrich_exchange_rates` into the generate-template flow**

In `import_pipeline.py`, find `generate_template_via_llm` caller (in `api/import_pipeline.py`'s `generate_template` endpoint). The enrichment happens in the API layer in Task 8. For now just verify the service builds:

```bash
cd backend && python -c "from app.services.import_pipeline import generate_template_via_llm, enrich_exchange_rates; print('OK')"
```

Expected: `OK`

---

## Task 8: API — Re-map, LLM Usage, Settings Display

**Files:**

- Modify: `backend/app/api/import_pipeline.py`
- Create: `backend/app/api/llm_usage.py`
- Modify: `backend/app/api/settings.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add re-map endpoint to `import_pipeline.py`**

At the end of `backend/app/api/import_pipeline.py`, add:

```python
@router.delete("/template/{platform_id}", status_code=204)
async def delete_template(
    platform_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ImportTemplate).where(
            ImportTemplate.platform_id == platform_id,
            ImportTemplate.user_id == current_user.id,
        )
    )
    tmpl = result.scalar_one_or_none()
    if tmpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.delete(tmpl)
    await db.commit()
    logger.info("ImportTemplate deleted (re-map): platform=%s user=%s", platform_id, current_user.id)
```

Also add `ImportTemplate` to the imports at the top if not already present:

```python
from app.models.import_template import ImportTemplate
```

- [ ] **Step 2: Wire exchange rate enrichment into `generate_template` endpoint**

In `api/import_pipeline.py`, find the `generate_template` endpoint and add enrichment after applying the template:

```python
# After: preview = pipeline_svc.apply_template(structure["all_rows"], template_data)
preview = await pipeline_svc.enrich_exchange_rates(db, preview)
```

- [ ] **Step 3: Create `backend/app/api/llm_usage.py`**

```python
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.llm_call_log import LLMCallLog
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter(prefix="/llm", tags=["llm-usage"])


@router.get("/call-logs")
async def get_call_logs(
    feature_key: Optional[str] = Query(default=None),
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(LLMCallLog).where(LLMCallLog.user_id == current_user.id)
    if feature_key:
        q = q.where(LLMCallLog.feature_key == feature_key)
    if from_date:
        q = q.where(LLMCallLog.created_at >= from_date)
    if to_date:
        q = q.where(LLMCallLog.created_at <= to_date)

    agg_q = select(
        func.sum(LLMCallLog.cost_usd).label("total_cost_usd"),
        func.sum(LLMCallLog.cost_thb).label("total_cost_thb"),
        func.sum(LLMCallLog.tokens_in).label("total_tokens_in"),
        func.sum(LLMCallLog.tokens_out).label("total_tokens_out"),
        func.count(LLMCallLog.id).label("total_calls"),
    ).where(LLMCallLog.user_id == current_user.id)
    if feature_key:
        agg_q = agg_q.where(LLMCallLog.feature_key == feature_key)
    if from_date:
        agg_q = agg_q.where(LLMCallLog.created_at >= from_date)
    if to_date:
        agg_q = agg_q.where(LLMCallLog.created_at <= to_date)

    logs_result = await db.execute(q.order_by(LLMCallLog.created_at.desc()).limit(limit).offset(offset))
    agg_result = await db.execute(agg_q)
    logs = logs_result.scalars().all()
    agg = agg_result.one()

    return {
        "total_cost_usd": float(agg.total_cost_usd or 0),
        "total_cost_thb": float(agg.total_cost_thb or 0),
        "total_tokens_in": int(agg.total_tokens_in or 0),
        "total_tokens_out": int(agg.total_tokens_out or 0),
        "total_calls": int(agg.total_calls or 0),
        "logs": [
            {
                "id": str(log.id),
                "feature_key": log.feature_key,
                "provider": log.provider,
                "model": log.model,
                "tokens_in": log.tokens_in,
                "tokens_out": log.tokens_out,
                "cost_usd": float(log.cost_usd),
                "cost_thb": float(log.cost_thb),
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }
```

- [ ] **Step 4: Add display settings endpoints to `backend/app/api/settings.py`**

Open the file and add at the end (after existing routes):

```python
from pydantic import BaseModel

class DisplaySettingsOut(BaseModel):
    currency_primary: str
    currency_secondary: str

class DisplaySettingsIn(BaseModel):
    currency_primary: str
    currency_secondary: str

@router.get("/settings/display", response_model=DisplaySettingsOut)
async def get_display_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return DisplaySettingsOut(
        currency_primary=current_user.currency_primary,
        currency_secondary=current_user.currency_secondary,
    )

@router.patch("/settings/display", response_model=DisplaySettingsOut)
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
```

Check what imports are already at the top of `settings.py` — add `AsyncSession`, `Depends`, `get_db`, `get_current_user`, `User` if missing.

- [ ] **Step 5: Register `llm_usage` router in `main.py`**

In `backend/app/main.py`, add to the import line:

```python
from app.api import analysis, assets, auth, cash_balance, documents, feature_llm_config, health, import_pipeline, llm_usage, overview, pipeline, platforms, portfolio, provider_config, settings
```

Add the router registration after the existing lines:

```python
app.include_router(llm_usage.router, prefix="/api/v1")
```

- [ ] **Step 6: Verify server starts**

```bash
cd backend && python -c "from app.main import app; print('OK')"
```

Expected: `OK`

---

## Task 9: AI Usage Frontend — Tabs + Summary Cards

**Files:**

- Modify: `frontend/app/(auth)/settings/ai/page.tsx`

- [ ] **Step 1: Read current AI page to understand its structure**

```bash
cat frontend/app/(auth)/settings/ai/page.tsx
```

Note: the existing components, API calls, and import paths before editing.

- [ ] **Step 2: Add API client function for call-logs**

In the page file (or in a shared `lib/api.ts` if one exists), add:

```typescript
async function fetchCallLogs(featureKey?: string): Promise<{
  total_cost_usd: number;
  total_cost_thb: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_calls: number;
  logs: Array<{
    id: string;
    feature_key: string;
    provider: string;
    model: string;
    tokens_in: number;
    tokens_out: number;
    cost_usd: number;
    cost_thb: number;
    created_at: string;
  }>;
}> {
  const params = featureKey ? `?feature_key=${featureKey}` : "";
  const res = await fetch(`/api/v1/llm/call-logs${params}`, {
    headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
  });
  if (!res.ok) throw new Error("Failed to fetch call logs");
  return res.json();
}
```

- [ ] **Step 3: Add state, tab, and summary cards to the AI page**

Replace the page content section with a tabbed layout. The exact implementation depends on what UI component library is used (shadcn/ui based on CLAUDE.md). Add:

```typescript
"use client";
import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Inside the component:
const [activeTab, setActiveTab] = useState("all");
const [data, setData] = useState<Awaited<
  ReturnType<typeof fetchCallLogs>
> | null>(null);
const [loading, setLoading] = useState(true);

useEffect(() => {
  const featureKey =
    activeTab === "import"
      ? "import_template_generator"
      : activeTab === "analysis"
        ? "portfolio_analysis"
        : undefined;
  setLoading(true);
  fetchCallLogs(featureKey)
    .then(setData)
    .finally(() => setLoading(false));
}, [activeTab]);
```

Summary cards (place above tabs):

```tsx
<div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm font-medium">Total Spend</CardTitle>
    </CardHeader>
    <CardContent>
      <p className="text-2xl font-bold">
        ฿{data?.total_cost_thb.toFixed(2) ?? "—"}
      </p>
      <p className="text-xs text-muted-foreground">
        ${data?.total_cost_usd.toFixed(4) ?? "—"} USD
      </p>
    </CardContent>
  </Card>
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm font-medium">Total Calls</CardTitle>
    </CardHeader>
    <CardContent>
      <p className="text-2xl font-bold">{data?.total_calls ?? "—"}</p>
    </CardContent>
  </Card>
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm font-medium">Tokens In</CardTitle>
    </CardHeader>
    <CardContent>
      <p className="text-2xl font-bold">
        {data?.total_tokens_in.toLocaleString() ?? "—"}
      </p>
    </CardContent>
  </Card>
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm font-medium">Tokens Out</CardTitle>
    </CardHeader>
    <CardContent>
      <p className="text-2xl font-bold">
        {data?.total_tokens_out.toLocaleString() ?? "—"}
      </p>
    </CardContent>
  </Card>
</div>
```

Tabs layout:

```tsx
<Tabs value={activeTab} onValueChange={setActiveTab}>
  <TabsList>
    <TabsTrigger value="all">All Calls</TabsTrigger>
    <TabsTrigger value="import">Import Mapping</TabsTrigger>
    <TabsTrigger value="analysis">Analysis</TabsTrigger>
  </TabsList>
  <TabsContent value={activeTab}>
    {loading ? (
      <p className="text-muted-foreground py-8 text-center">Loading...</p>
    ) : (
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="text-left py-2">Date</th>
            <th className="text-left py-2">Feature</th>
            <th className="text-left py-2">Provider / Model</th>
            <th className="text-right py-2">Tokens In</th>
            <th className="text-right py-2">Tokens Out</th>
            <th className="text-right py-2">Cost (THB)</th>
          </tr>
        </thead>
        <tbody>
          {data?.logs.map((log) => (
            <tr key={log.id} className="border-b hover:bg-muted/50">
              <td className="py-2">
                {new Date(log.created_at).toLocaleDateString()}
              </td>
              <td className="py-2">{log.feature_key.replace(/_/g, " ")}</td>
              <td className="py-2">
                {log.provider} / {log.model}
              </td>
              <td className="py-2 text-right">
                {log.tokens_in.toLocaleString()}
              </td>
              <td className="py-2 text-right">
                {log.tokens_out.toLocaleString()}
              </td>
              <td className="py-2 text-right">฿{log.cost_thb.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )}
  </TabsContent>
</Tabs>
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: No errors (or only pre-existing unrelated errors).

---

## Task 10: Currency Preference UI + Re-map Button

**Files:**

- Modify: `frontend/app/(auth)/settings/page.tsx`
- Modify: `frontend/app/(auth)/import/page.tsx`

- [ ] **Step 1: Read both files**

```bash
cat frontend/app/(auth)/settings/page.tsx | head -60
cat frontend/app/(auth)/import/page.tsx | head -60
```

Note existing component patterns and import styles before editing.

- [ ] **Step 2: Add currency preference section to `settings/page.tsx`**

Add a "Display" section with two selects. Add below the existing settings sections:

```tsx
const CURRENCIES = ["THB", "USD", "EUR", "GBP", "JPY", "SGD"];

// State:
const [currencyPrimary, setCurrencyPrimary] = useState("THB");
const [currencySecondary, setCurrencySecondary] = useState("USD");

// Load on mount:
useEffect(() => {
  fetch("/api/v1/settings/display", {
    headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
  })
    .then((r) => r.json())
    .then((d) => {
      setCurrencyPrimary(d.currency_primary);
      setCurrencySecondary(d.currency_secondary);
    });
}, []);

// Save handler:
async function saveCurrencyPrefs() {
  await fetch("/api/v1/settings/display", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${localStorage.getItem("token")}`,
    },
    body: JSON.stringify({
      currency_primary: currencyPrimary,
      currency_secondary: currencySecondary,
    }),
  });
}
```

UI section:

```tsx
<Card>
  <CardHeader>
    <CardTitle>Display</CardTitle>
  </CardHeader>
  <CardContent className="space-y-4">
    <div className="flex gap-4 items-end">
      <div className="flex-1">
        <label className="text-sm font-medium mb-1 block">
          Primary Currency
        </label>
        <select
          className="w-full border rounded px-3 py-2 text-sm"
          value={currencyPrimary}
          onChange={(e) => setCurrencyPrimary(e.target.value)}
        >
          {CURRENCIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <div className="flex-1">
        <label className="text-sm font-medium mb-1 block">
          Secondary Currency
        </label>
        <select
          className="w-full border rounded px-3 py-2 text-sm"
          value={currencySecondary}
          onChange={(e) => setCurrencySecondary(e.target.value)}
        >
          {CURRENCIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <button
        onClick={saveCurrencyPrefs}
        className="px-4 py-2 bg-primary text-primary-foreground rounded text-sm"
      >
        Save
      </button>
    </div>
  </CardContent>
</Card>
```

- [ ] **Step 3: Add Re-map button to `import/page.tsx`**

Find where platform is selected or where the template status is shown. Add a Re-map button that appears when a template exists (status = "match"):

```tsx
// Handler:
async function handleRemap(platformId: string) {
  if (
    !confirm(
      "Delete the saved mapping for this platform? The next upload will ask the AI to re-learn the format.",
    )
  )
    return;
  await fetch(`/api/v1/import/template/${platformId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
  });
  // Reset template status in local state to trigger fresh analysis
  setTemplateStatus("new");
}
```

Button (show only when `templateStatus === "match"`):

```tsx
{
  templateStatus === "match" && selectedPlatformId && (
    <button
      onClick={() => handleRemap(selectedPlatformId)}
      className="text-sm text-destructive underline"
    >
      Re-map (re-learn format)
    </button>
  );
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: No errors.

---

## Self-Review Checklist

After completing all tasks, verify spec coverage:

- [ ] Canonical schema (`CANONICAL_FIELDS`) — Task 1 ✅
- [ ] `apply_template` with value_transforms, derived_fields, defaults — Task 1 ✅
- [ ] Historical exchange rate (BOT/CDN API + DB cache) — Task 4 ✅
- [ ] `llm_call_logs` table — Task 2 + 3 ✅
- [ ] All LLM adapters return `LLMResponse` with tokens — Task 6 ✅
- [ ] Gemini token extraction fix — Task 5 ✅
- [ ] `LLMGateway.complete()` auto-logs every call — Task 6 ✅
- [ ] Updated LLM prompts (new canonical fields in system prompt) — Task 7 ✅
- [ ] `ImportTemplate` extended with new JSONB columns — Task 3 ✅
- [ ] Exchange rate enrichment per row — Task 7 ✅
- [ ] `DELETE /import/template/{platform_id}` re-map endpoint — Task 8 ✅
- [ ] `GET /llm/call-logs` with filters + aggregation — Task 8 ✅
- [ ] `PATCH /settings/display` currency preference — Task 8 ✅
- [ ] AI Usage page tabs + summary cards — Task 9 ✅
- [ ] Currency dropdowns in Settings page — Task 10 ✅
- [ ] Re-map button in Import page — Task 10 ✅
