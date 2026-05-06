# Settings Page — Telegram & Privacy — Design Spec

**Date:** 2026-05-06
**Status:** Approved
**Replaces:** 2026-05-06-user-settings-universe-design.md (dropped — user_settings table not needed)
**Kanban:** feat - settings page full UI - remaining tabs

---

## Context

The settings page has two tabs: General (hardware, display, profile) and AI & LLM. The backend already has Telegram endpoints (`GET/PUT /settings/telegram`, `POST /settings/telegram/test`) but no UI tab. Privacy mode exists only in localStorage — needs backend storage.

---

## Scope

Two additions:
1. **Backend:** `privacy_mode` field on `User` model + `GET/PATCH /settings/privacy` endpoint
2. **UI:** Telegram tab in settings page
3. **UI:** Privacy card in General tab

No new tables. No user_settings table. Everything stays on the `User` model.

---

## Backend

### Migration

Add `privacy_mode` boolean column to `users` table:

```
privacy_mode: Boolean, default=False, nullable=False
```

### New endpoints

**`GET /settings/privacy`**
- Returns `{ privacy_mode: bool }` from `current_user`

**`PATCH /settings/privacy`**
- Body: `{ privacy_mode: bool }`
- Updates `current_user.privacy_mode`, commits, returns updated value

---

## UI

### Tab 1: General tab (existing) — add Privacy card

New card at the bottom of General tab:

**Privacy**
- Toggle: "Privacy Mode" — hides portfolio values across the app
- On toggle → immediately `PATCH /settings/privacy` with new value
- On page load → `GET /settings/privacy` pre-fills the toggle
- Toast on error only (success is silent for toggles)

### Tab 2: New "Notifications" tab

Contains one card: **Telegram Alerts**

Fields:
- Bot Token input (password type, masked)
- Chat ID input
- Save button → `PUT /settings/telegram`
- Test button → `POST /settings/telegram/test` → toast success/error

On page load → `GET /settings/telegram`:
- If `has_token: true` → show masked placeholder in token field (`••••••••`)
- Pre-fill chat_id if present

---

## Out of Scope

- Universe symbol list (dropped — discover job uses LLM knowledge directly)
- user_settings table (not needed — User model handles all current prefs)
- Line bot notifications (backlog)
- Email notifications (backlog)
