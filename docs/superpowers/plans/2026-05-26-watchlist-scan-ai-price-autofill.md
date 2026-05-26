# Watchlist Scan AI Price Auto-Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a watchlist scan, the AI Price column always shows a price target and the Target / % to Target columns auto-fill from it.

**Architecture:** Tighten the `_parse_scan_response` validator to reject null `suggested_price`, update the `watchlist_scan` system prompt to always require a numeric price target, and backfill `WatchlistItem.target_price` from the AI result at the end of the scan job.

**Tech Stack:** Python, SQLAlchemy async, pytest (asyncio_mode=auto), ARQ worker

---

## File Map

| File | Change |
|------|--------|
| `backend/worker/jobs/watchlist_scan.py` | Tighten `_parse_scan_response`; backfill `WatchlistItem.target_price` in step 4 |
| `backend/app/services/llm_gateway.py` | Update `watchlist_scan` system prompt: require numeric price, add HOLD/AVOID guidance |
| `backend/tests/test_watchlist_scan.py` | New file — unit tests for `_parse_scan_response` |

---

## Task 1: Tighten `_parse_scan_response` validation (TDD)

**Files:**
- Create: `backend/tests/test_watchlist_scan.py`
- Modify: `backend/worker/jobs/watchlist_scan.py:20-31`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_watchlist_scan.py`:

```python
import math
from worker.jobs.watchlist_scan import _parse_scan_response


def test_valid_buy_response():
    raw = '{"verdict": "BUY", "suggested_price": 150.5, "reasoning": "strong momentum"}'
    result = _parse_scan_response(raw)
    assert result == {"verdict": "BUY", "suggested_price": 150.5, "reasoning": "strong momentum"}


def test_valid_hold_response_with_price():
    raw = '{"verdict": "HOLD", "suggested_price": 200.0, "reasoning": "wait for pullback"}'
    result = _parse_scan_response(raw)
    assert result["verdict"] == "HOLD"
    assert result["suggested_price"] == 200.0


def test_missing_suggested_price_returns_none():
    raw = '{"verdict": "BUY", "reasoning": "good stock"}'
    assert _parse_scan_response(raw) is None


def test_null_suggested_price_returns_none():
    raw = '{"verdict": "HOLD", "suggested_price": null, "reasoning": "no price"}'
    assert _parse_scan_response(raw) is None


def test_string_suggested_price_returns_none():
    raw = '{"verdict": "BUY", "suggested_price": "150.5", "reasoning": "ok"}'
    assert _parse_scan_response(raw) is None


def test_nan_suggested_price_returns_none():
    # math.isfinite rejects NaN/Inf passed as Python float via crafted input
    import json
    data = {"verdict": "BUY", "suggested_price": float("inf"), "reasoning": "x"}
    raw = json.dumps(data)
    # json.dumps converts inf to a non-standard form; json.loads rejects it
    # so this tests the path where parsing succeeds but value is invalid
    assert _parse_scan_response(raw) is None


def test_code_block_wrapping_still_works():
    raw = '```json\n{"verdict": "HOLD", "suggested_price": 99.99, "reasoning": "fair value"}\n```'
    result = _parse_scan_response(raw)
    assert result is not None
    assert result["suggested_price"] == 99.99


def test_avoid_verdict_with_price():
    raw = '{"verdict": "AVOID", "suggested_price": 50.0, "reasoning": "overvalued"}'
    result = _parse_scan_response(raw)
    assert result is not None
    assert result["verdict"] == "AVOID"


def test_invalid_verdict_returns_none():
    raw = '{"verdict": "MAYBE", "suggested_price": 100.0, "reasoning": "dunno"}'
    assert _parse_scan_response(raw) is None


def test_malformed_json_returns_none():
    assert _parse_scan_response("not json at all") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
docker compose exec -T worker python -m pytest tests/test_watchlist_scan.py -v 2>&1 | tail -30
```

Expected: Several FAIL/ERROR results (function not yet updated).

- [ ] **Step 3: Update `_parse_scan_response` to enforce numeric `suggested_price`**

In `backend/worker/jobs/watchlist_scan.py`, replace the existing `_parse_scan_response` function (lines 20–31):

```python
def _parse_scan_response(text: str) -> dict | None:
    import math
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        data = json.loads(text)
        if data.get("verdict") not in ("BUY", "SELL", "HOLD", "AVOID"):
            return None
        price = data.get("suggested_price")
        if not isinstance(price, (int, float)) or not math.isfinite(price):
            return None
        return data
    except (json.JSONDecodeError, AttributeError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
docker compose exec -T worker python -m pytest tests/test_watchlist_scan.py -v 2>&1 | tail -20
```

Expected: All 9 tests PASS.

---

## Task 2: Update the `watchlist_scan` system prompt

**Files:**
- Modify: `backend/app/services/llm_gateway.py:170-177`

No test needed — this is a prompt string change; correctness is validated by the tightened parser in Task 1.

- [ ] **Step 1: Update the system prompt**

In `backend/app/services/llm_gateway.py`, replace the `watchlist_scan` entry in `SYSTEM_PROMPTS` (lines 170–177):

```python
    "watchlist_scan": (
        "You are a financial analyst evaluating an asset as a potential buy opportunity. "
        "The user does not currently hold this asset. Analyze the recent price history and research context. "
        "Respond ONLY with valid JSON in this exact format — no text outside the object:\n"
        "{\"verdict\": \"BUY\" | \"HOLD\" | \"AVOID\", "
        "\"suggested_price\": <number>, "
        "\"reasoning\": \"<2-3 sentence explanation>\"}\n\n"
        "Rules for suggested_price:\n"
        "- Always provide a numeric value. Never use null.\n"
        "- BUY: the specific entry price you recommend buying at.\n"
        "- HOLD: the price level to watch for entry (support or fair value).\n"
        "- AVOID: the price at which the thesis would become attractive.\n"
        "Use the most recent price in the history as your reference point."
    ),
```

- [ ] **Step 2: Verify the prompt renders with the current user template**

The user template (`USER_PROMPTS["watchlist_scan"]`) is:
```
Asset: {symbol}\n\nRecent price history (last 10 days):\n{prices_txt}\n\nResearch context:\n{rag_context}\n\nShould I buy this asset? Provide your JSON verdict.
```
No changes needed there. Confirm the system prompt key name matches exactly: `"watchlist_scan"` — it does.

---

## Task 3: Backfill `WatchlistItem.target_price` in the scan job

**Files:**
- Modify: `backend/worker/jobs/watchlist_scan.py:96-115`

- [ ] **Step 1: Add the backfill in step 4 of `job_scan_watchlist_item`**

In `backend/worker/jobs/watchlist_scan.py`, replace the `# Step 4: save_suggestion` block (lines 96–115):

```python
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
            item.target_price = Decimal(str(parsed["suggested_price"]))
            await db.commit()
            await finish_step(db, step_save, success=True, metadata={"symbol": asset.symbol, "verdict": parsed["verdict"]})
            await finish_log(db, log, success=True)
            logger.info("watchlist_scan done item=%s verdict=%s target_price=%s", item_id, parsed["verdict"], item.target_price)
            return {"verdict": parsed["verdict"], "analysis_id": str(analysis.id)}
```

- [ ] **Step 2: Verify `Decimal` is already imported**

Check the top of `backend/worker/jobs/watchlist_scan.py`. There is no `Decimal` import currently. Add it to the imports:

```python
from decimal import Decimal
```

The full updated import block at the top of the file should be:

```python
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.asset import Asset
from app.models.price import Price
from app.models.watchlist_item import WatchlistItem
from app.services.llm_gateway import LLMGateway
from app.services.pipeline import create_log, finish_log, create_step, finish_step
from app.services.rag_service import get_or_create_collection, search
```

- [ ] **Step 3: Run the full test suite to check for regressions**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
docker compose exec -T worker python -m pytest tests/test_watchlist_scan.py tests/services/test_llm_gateway.py -v 2>&1 | tail -30
```

Expected: All tests PASS.

- [ ] **Step 4: Manual smoke test**

Trigger a single watchlist scan from the UI (click the expand icon on any row → scan, or use "Scan All"). Check the worker logs:

```
watchlist_scan done item=<uuid> verdict=HOLD target_price=<number>
```

Reload the watchlist page. The Target and AI Price columns should now show a number instead of `—`.
