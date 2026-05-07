# Dividend Telegram Alert — Design Spec

**Date:** 2026-05-08  
**Status:** Approved

## Summary

Send a Telegram notification to the user at 13:00 Bangkok (06:00 UTC) on each stock's ex-dividend date, but only for stocks they actually hold (quantity > 0). Message includes the projected total income in both USD and secondary currency (THB).

## Trigger

- **When:** ex-dividend date = today, at 13:00 GMT+7 (06:00 UTC) daily cron
- **Filter:** `holding.quantity > 0` AND `dividend_notified_at IS NULL`
- **Scope:** all users with Telegram configured

## Data Model Change

Add one nullable column to `dividend_event`:

```sql
dividend_notified_at TIMESTAMP WITH TIME ZONE DEFAULT NULL
```

Stamped after a successful Telegram send. Prevents duplicate notifications if the job runs more than once in a day.

Two new migrations:
- **029** — add `dividend_notified_at` to `dividend_event`
- **030** — add `dividend_alert` to `job_type_enum`

## Service: `app/services/dividend_alert.py`

Single public function: `check_and_notify(db: AsyncSession) -> int`

**Query:** `DividendEvent JOIN Asset JOIN Holding JOIN User` where:
- `DividendEvent.ex_date = date.today()`
- `Holding.quantity > 0`
- `DividendEvent.dividend_notified_at IS NULL`
- `Holding.user_id = User.id`

**Per row:**
1. Skip if user has no `telegram_bot_token` or `telegram_chat_id`
2. Fetch exchange rate via `get_rate(db, "USD", user.currency_secondary)`
3. Compute projected total = `holding.quantity × event.amount_per_share`
4. Format and send Telegram message
5. Stamp `dividend_notified_at = now()` and commit

**Message format (HTML):**
```
💰 <b>Dividend Day — {symbol}</b>

Ex-dividend date: {ex_date}
Amount/share: {amount_per_share} {currency}
Shares held: {quantity}
Projected income: <b>{total} {currency} (~{total_secondary} {secondary_currency})</b>
```

Uses existing `decrypt(user.telegram_bot_token)` and `send_message()` from `app/services/telegram.py`.

## Worker Job: `worker/jobs/dividend_alert.py`

```python
async def job_dividend_alert(ctx):
    # create_log(db, "dividend_alert")
    # check_and_notify(db)
    # finish_log(db, log, success=True)
```

Follows `job_check_watchlist_alerts` pattern exactly.

## Registration: `worker/main.py`

- Add `job_dividend_alert` to `functions` list
- Add cron: `cron(job_dividend_alert, hour=6, minute=0)` (06:00 UTC = 13:00 GMT+7)

## Model Update: `app/models/pipeline_log.py`

Add `"dividend_alert"` to `JOB_TYPES` tuple.

## Files Changed

| File | Change |
|---|---|
| `alembic/versions/029_add_dividend_notified_at.py` | New migration |
| `alembic/versions/030_add_dividend_alert_job_type.py` | New migration |
| `app/models/dividend_event.py` | Add `dividend_notified_at` column |
| `app/models/pipeline_log.py` | Add `"dividend_alert"` to `JOB_TYPES` |
| `app/services/dividend_alert.py` | New service |
| `worker/jobs/dividend_alert.py` | New ARQ job |
| `worker/main.py` | Register job + cron |

## Out of Scope

- Pay-date notifications (user chose ex-date only)
- Notification history UI
- Per-stock opt-out toggle
