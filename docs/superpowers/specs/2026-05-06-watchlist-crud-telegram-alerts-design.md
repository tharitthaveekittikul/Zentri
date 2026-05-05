# Watchlist CRUD + Telegram Price Alerts — Design Spec

**Date:** 2026-05-06
**Scope:** Watchlist backend CRUD, Telegram alert config in settings, ARQ alert job

---

## Overview

Users can add assets to a watchlist with an optional target buy price. When the price fetch worker detects that a watched asset's current price has dropped to or below the target, it enqueues a separate ARQ alert job that sends a Telegram message. The alert fires once and marks itself as sent (`alerted_at`) — the user must manually re-arm it.

---

## Data Model

### Migration `014_watchlist.py` — `watchlist_items` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `uuid4` default |
| `user_id` | UUID FK → users | indexed |
| `asset_id` | UUID FK → assets | |
| `target_price` | Numeric(20,8) | nullable |
| `currency` | String(10) | default "USD" |
| `notes` | Text | nullable |
| `alert_enabled` | Boolean | default True |
| `alerted_at` | DateTime(timezone=True) | nullable — null = armed, set = fired |
| `created_at` | DateTime(timezone=True) | default `utcnow` |

### Migration `015_telegram_config.py` — add columns to `users` table

| Column | Type | Notes |
|---|---|---|
| `telegram_bot_token` | Text nullable | AES-256 encrypted (same pattern as LLM API keys) |
| `telegram_chat_id` | String(100) nullable | |

---

## API Endpoints

### Watchlist — `backend/app/api/watchlist.py`, prefix `/watchlist`

| Method | Path | Description |
|---|---|---|
| `GET` | `/watchlist` | List all items; join current price, include `%_from_target` |
| `POST` | `/watchlist` | Add asset to watchlist |
| `PATCH` | `/watchlist/{id}` | Update `target_price`, `notes`, or `alert_enabled` |
| `DELETE` | `/watchlist/{id}` | Remove item |
| `POST` | `/watchlist/{id}/rearm` | Clear `alerted_at` to re-arm alert |

### Telegram settings — added to existing `backend/app/api/settings.py`

| Method | Path | Description |
|---|---|---|
| `PUT` | `/settings/telegram` | Save `bot_token` + `chat_id` (encrypted before persist) |
| `POST` | `/settings/telegram/test` | Send test Telegram message to verify config |

### Telegram Settings UI — Setup Guidance

The settings form must include inline guidance so users know how to obtain credentials. Implementation: a collapsible **"How to set up"** section (accordion or `<details>`) above the input fields — not a tooltip, since the steps are multi-line.

**Bot Token — step-by-step:**
1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts to name your bot
3. Copy the token BotFather gives you (format: `123456:ABC-DEF...`)

**Chat ID — step-by-step:**
1. Start a chat with your new bot (search its username, press Start)
2. Send any message to it
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
4. Copy the `chat.id` value from the response (a number like `987654321`)

The "Test" button sends a message immediately using the currently saved config and shows a success toast or inline error — so the user knows it works before leaving the page.

---

## Services

### `backend/app/services/watchlist_alert.py`

- `check_and_notify(db, redis)` — main entry point for the ARQ job
  - Queries `watchlist_items` where `alert_enabled=True`, `alerted_at IS NULL`, `target_price IS NOT NULL`
  - Joins latest price from `prices` table
  - For each item where `current_price <= target_price`: sends Telegram message, sets `alerted_at = utcnow()`
  - Failures on individual items are logged and skipped — job continues

### `backend/app/services/telegram.py`

- `send_message(bot_token, chat_id, text)` — thin async wrapper over Telegram Bot API
- `get_telegram_config(db, user_id)` — load + decrypt bot_token from user record

---

## Worker Jobs

### `backend/worker/jobs/watchlist_alert.py`

- `job_check_watchlist_alerts(ctx)` — calls `watchlist_alert.check_and_notify()`
- Registered in worker's job list

### Price fetch job modification

After successful price update, enqueue `job_check_watchlist_alerts`:
```python
await ctx["redis"].enqueue_job("job_check_watchlist_alerts")
```

---

## Schemas — `backend/app/schemas/watchlist.py`

- `WatchlistItemCreate` — `asset_id`, `target_price?`, `currency`, `notes?`
- `WatchlistItemUpdate` — `target_price?`, `notes?`, `alert_enabled?`
- `WatchlistItemOut` — all fields + `current_price`, `pct_from_target`, `asset` (symbol, name)

---

## Error Handling

| Scenario | Response |
|---|---|
| Add asset already in watchlist | `409 Conflict` |
| PATCH/DELETE/rearm on item not owned by user | `404 Not Found` (don't leak existence) |
| Telegram test with no config saved | `400 Bad Request` |
| Telegram API call fails (bad token/chat_id) | `502 Bad Gateway` with Telegram error detail |
| Alert job: single item Telegram send fails | Log error, continue to next item |

---

## Testing

- `backend/tests/services/test_watchlist_alert.py`
  - Mock Telegram HTTP call — verify `alerted_at` is set on hit
  - Verify already-alerted items (`alerted_at IS NOT NULL`) are skipped
  - Verify items with `alert_enabled=False` are skipped
- API-level tests: 409 duplicate, 404 ownership enforcement

---

## Files to Create / Modify

| Action | Path |
|---|---|
| Create | `backend/alembic/versions/014_watchlist.py` |
| Create | `backend/alembic/versions/015_telegram_config.py` |
| Create | `backend/app/models/watchlist_item.py` |
| Modify | `backend/app/models/user.py` (add telegram columns) |
| Create | `backend/app/schemas/watchlist.py` |
| Create | `backend/app/api/watchlist.py` |
| Modify | `backend/app/api/settings.py` (add telegram endpoints) |
| Modify | `backend/app/main.py` (register watchlist router) |
| Create | `backend/app/services/watchlist_alert.py` |
| Create | `backend/app/services/telegram.py` |
| Create | `backend/worker/jobs/watchlist_alert.py` |
| Modify | `backend/worker/jobs/price_fetch.py` (enqueue alert job) |
| Modify | `backend/worker/main.py` (register new job) |
| Create | `backend/tests/services/test_watchlist_alert.py` |
