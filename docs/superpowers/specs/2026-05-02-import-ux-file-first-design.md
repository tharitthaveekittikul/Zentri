# Import UX Redesign — File-First Wizard

**Date:** 2026-05-02  
**Status:** Approved — ready for implementation

---

## Problem

The current import flow forces users to pre-create a Platform in Settings before they can import any file. This creates unnecessary friction (two-page journey before seeing the wizard) and the platform dropdown is empty on first use. Additionally, the platform is not saved on transactions, so there is no source tag visible in the portfolio.

---

## Goals

1. Remove the mandatory platform pre-setup — users should be able to import on first visit.
2. Platform name is assigned inline during import (created on the spot if new).
3. Platform is stored as a source tag on every imported transaction.
4. Portfolio page links to the Import page via an "Import" button.
5. Settings manages existing platforms (rename / delete).

---

## Approach: File-First Wizard

User uploads the file first. The system analyzes it and only asks for a platform name if it cannot match an existing template by column signature.

---

## User Flow

| Step | Condition | What happens |
|------|-----------|-------------|
| 1. Upload | Always | User selects CSV or JSON file. No platform selection yet. |
| 2. Analyze | Always | Backend detects format, reads headers, matches column signature against all user templates. |
| 3. Name Source | New or mismatched template only | Text input "What do you call this broker/platform?" with existing platforms as quick-select chips. Creates platform inline if name is new. |
| 4. Review | Always | Preview table (first 20 rows). Shows platform name as source. Confirm or go back. |
| 5. Done | Always | Success count + "Go to Portfolio" link. |

**Happy path (repeat import, same broker):** Steps 1 → 2 → 4 → 5. Platform name step is skipped entirely.  
**First-time or new broker:** Steps 1 → 2 → 3 → 4 → 5.  
**Column structure changed:** Steps 1 → 2 → 3 (re-generate template) → 4 → 5.

---

## Backend Changes

### Transaction model
- Add `platform_id: UUID | None` FK to `platforms.id` (nullable for backward compatibility).

### `/import/analyze` endpoint
- `platform_id` becomes **optional**.
- When omitted, search for a matching template by `(user_id, column_signature)` across all platforms.
- Return `matched_platform` in response if a template is found.

### `/import/confirm` endpoint
- Accept `platform_id` in request body.
- Save `platform_id` on each created transaction.

### Inline platform creation
- Reuse existing platform CRUD (`POST /platforms`) called from frontend when user types a new name in step 3.
- No new endpoint needed.

### Alembic migration
- Add `platform_id` nullable column to `transactions` table.

---

## Frontend Changes

### `frontend/app/(auth)/import/page.tsx`
- Remove platform dropdown from step 1 (Upload).
- Add new step 3 "Name Source" between Analyze and Review:
  - Text input for new platform name.
  - Quick-select chips showing existing platforms.
  - On confirm: `POST /platforms` if new name, then continue.
- Pass `platform_id` to `/import/confirm`.
- Show platform name in the Review step preview header.

### `frontend/app/(auth)/portfolio/page.tsx`
- Add "Import" button to page header, routes to `/import`.

### `frontend/app/(auth)/settings/page.tsx`
- Add "Platforms" section: list platforms with rename and delete.

---

## Data Model

```
Platform
  id, user_id, name, asset_types_supported, notes, created_at

Transaction (existing)
  + platform_id: UUID | null  ← new column
```

---

## Out of Scope

- Auto-detecting the platform name from file content (future).
- Showing platform filter in Portfolio (future).
- Platform-level import history (future).
