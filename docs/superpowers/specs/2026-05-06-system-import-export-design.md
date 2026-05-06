# System Import/Export — Design Spec

**Date:** 2026-05-06  
**Status:** Approved

## Overview

A full system backup and restore feature. Export produces a single versioned JSON file containing all user data. Import does a full replace — wiping existing data and restoring from the file. Exposed in two places: a dedicated Settings → Backup & Restore page, and a new wizard step during initial setup.

---

## Backup Payload Format

```json
{
  "version": "1",
  "exported_at": "2026-05-06T...",
  "settings": {
    "currency_primary": "THB",
    "currency_secondary": "USD",
    "birth_date": "1990-01-01",
    "plan_to_age": 85,
    "privacy_mode": false,
    "telegram_chat_id": "...",
    "telegram_bot_token": "..."
  },
  "portfolio": {
    "holdings": [
      { "symbol": "AAPL", "asset_type": "stock", "quantity": 10, "avg_cost_price": 150.0, "currency": "USD", "platform": "ibkr", "purchased_at": "2024-01-01" }
    ],
    "transactions": [
      { "symbol": "AAPL", "asset_type": "stock", "type": "buy", "quantity": 10, "price": 150.0, "fee": 1.5, "source": "manual", "executed_at": "2024-01-01T00:00:00Z", "platform": "ibkr" }
    ]
  },
  "provider_configs": [
    { "provider": "anthropic", "api_key": "sk-ant-...", "host_url": null, "is_connected": true }
  ],
  "feature_llm_configs": [
    { "feature_key": "portfolio_analysis", "provider": "anthropic", "model": "claude-sonnet-4-6", "system_prompt": "...", "is_prompt_customized": false }
  ],
  "watchlist": [
    { "symbol": "NVDA", "asset_type": "stock", "notes": "...", "created_at": "2025-01-01T00:00:00Z" }
  ],
  "cash_balances": [
    { "currency": "THB", "amount": 50000, "label": "Savings", "date": "2026-01-01" }
  ],
  "ai_analyses": [
    {
      "symbol": "AAPL",
      "verdict": "buy",
      "target_price": 200.0,
      "reasoning": "...",
      "provider": "anthropic",
      "model": "claude-sonnet-4-6",
      "created_at": "2026-01-01T00:00:00Z",
      "conversations": [
        { "role": "user", "content": "...", "message_order": 1 },
        { "role": "assistant", "content": "...", "message_order": 2 }
      ]
    }
  ]
}
```

**Not included:** AI usage logs (`llm_call_log`), price history, exchange rate cache, pipeline logs, documents.

**Security note:** `provider_configs[].api_key` and `settings.telegram_bot_token` are exported as plaintext. The UI must display a warning.

---

## Backend

### New files

| File | Purpose |
|---|---|
| `backend/app/api/system.py` | Two endpoints: export + import |
| `backend/app/services/system_backup.py` | Export and import business logic |

### Endpoints

**`GET /system/export`**
- Auth required
- Queries all sections for `current_user`
- Decrypts API keys before serialization
- Serializes assets by symbol (not UUID) for portability
- Returns `application/json` with `Content-Disposition: attachment; filename=zentri-backup-YYYY-MM-DD.json`

**`POST /system/import`**
- Auth required
- Accepts multipart file upload (field name: `file`)
- Validates `version` field — returns `400` with clear message if unsupported
- Shows security warning that this is destructive
- Wipe + restore order:
  1. Wipe: `feature_llm_configs` → `ai_analyses` + `llm_conversations` → `cash_balances` → `watchlist_items` → `transactions` → `holdings` → `provider_configs` → user settings fields
  2. Restore in reverse order; assets re-looked-up or created by symbol

### Registration

Add `system` router to `backend/app/main.py`.

---

## Frontend

### New files

| File | Purpose |
|---|---|
| `frontend/app/(auth)/settings/backup/page.tsx` | Dedicated backup & restore page |
| `frontend/lib/services/system.ts` | `exportSystem()` + `importSystem(file)` API client |

### Settings Backup Page (`/settings/backup`)

- **Export section**: "Download Backup" button → calls `GET /system/export` → auto-downloads JSON file
- **Security warning banner** (yellow/amber): "This backup file contains plaintext API keys. Do not share it."
- **Import section**: `.json` file dropzone, shows selected filename
- **Import confirmation dialog**: "This will permanently replace ALL your data. This cannot be undone." with Cancel / Confirm buttons
- Success/error feedback via `sonner` toast

### Wizard — Restore Step

Inserted as Step 2 of 5 (after account creation, before profile). Progress percentages update to 20/40/60/80/100.

- New step key: `"restore"` added to `Step` type in `setup/page.tsx`
- Card: "Restore from backup?" with subtitle "Step 2 of 5 — Optional"
- Two actions: "Upload backup file" (file input) + "Start fresh" (skip)
- On upload + confirm: calls `POST /system/import`, redirects to `/` on success (skips remaining setup steps)
- On skip: proceeds to `"profile"` step as before

### Settings nav

Add "Backup & Restore" link pointing to `/settings/backup`.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Invalid JSON file | `400` from backend; toast "Invalid backup file" |
| Unsupported version | `400` from backend; toast "Backup version not supported" |
| Import partially fails | Transaction rollback; no partial state; toast with error detail |
| Export while no data | Returns valid JSON with empty arrays — no error |
