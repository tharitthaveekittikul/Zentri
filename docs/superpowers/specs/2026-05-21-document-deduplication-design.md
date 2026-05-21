# Document Deduplication & Documents Page Fix

**Date:** 2026-05-21  
**Status:** Approved

---

## Problem

1. **Duplicate system downloads.** `run_top_down_analysis` calls `DocumentManager.pre_fetch()` which deduplicates by `source_url`. When `discover_top_down` queues the same ticker concurrently, both jobs call `check_exists()` before either commits — a race condition — resulting in identical files stored twice.

2. **Manual upload has no dedup.** `POST /documents/upload` saves every upload unconditionally; the same file uploaded twice creates two records.

3. **Documents page silent failure.** If `GET /api/v1/documents` returns a non-200 response, the page shows an empty table with no indication of error. Users cannot distinguish "no documents" from "something went wrong."

---

## Solution Overview

- Add `content_hash` (SHA-256) column to `documents` with a DB unique constraint as the authoritative dedup guard — race-condition-proof by definition.
- Apply hash check in both `pre_fetch()` (system downloads) and `POST /documents/upload` (manual uploads).
- Manual upload: return `409 Conflict` with existing doc info when a duplicate is detected; frontend shows a "Replace existing?" modal.
- Documents page: show a visible error state instead of an empty table when the API call fails.

---

## Data Layer

**New column:** `content_hash VARCHAR(64) NULLABLE` on the `documents` table.

**Unique constraint:** Partial unique index `WHERE content_hash IS NOT NULL` — so existing rows with `NULL` are unaffected and new rows with identical content are rejected by the DB.

**Migration:** New Alembic revision (do not edit existing migrations). Existing rows keep `content_hash = NULL`.

---

## Backend

### `Document` model (`backend/app/models/document.py`)

Add field:
```python
content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=False)
```
The unique constraint is on the DB level via migration (partial index), not via SQLAlchemy `unique=True`, to keep it nullable-safe.

### `DocumentManager.pre_fetch()` (`backend/app/services/document_manager.py`)

1. After downloading bytes, compute `hashlib.sha256(content).hexdigest()`.
2. Query DB for existing document with that hash before inserting.
3. If found: log as skipped, increment `skipped`, continue. (URL-based `check_exists()` remains as a fast pre-filter to avoid unnecessary downloads.)
4. Save `content_hash` on the new `Document` record.
5. If a DB `UniqueViolationError` is raised on insert (concurrent race): catch it, treat as skipped, do not re-raise.

### `POST /documents/upload` (`backend/app/api/documents.py`)

1. Read file bytes, compute SHA-256 hash.
2. Query DB for existing document with that hash.
3. If found and no `replace_id` in query params: return `HTTP 409` with body `{"existing_id": "...", "existing_filename": "..."}`. Do **not** save the file to disk.
4. If `replace_id` query param is present:
   - Load the document by `replace_id`.
   - Delete its Chroma collection (if any).
   - Delete its file from disk (if exists).
   - Delete the DB record.
   - Save the new file and create a new `Document` record with `content_hash`.
5. Normal upload (no duplicate): save file and record with `content_hash` as before.

---

## Frontend

### Documents page upload flow (`frontend/app/(auth)/documents/page.tsx`)

- After `uploadWithAuth()` resolves, check response status.
- On `409`: parse `{existing_id, existing_filename}` from body, show a confirmation dialog: *"A file with identical content already exists as `[filename]`. Replace it?"* with **Cancel** and **Replace** buttons.
- On **Replace**: call `uploadWithAuth` again with `?replace_id=<existing_id>` appended to the URL, then reload.
- On **Cancel**: close dialog, no action.

### Documents page error state (`frontend/app/(auth)/documents/page.tsx`)

- Add `error: string | null` state.
- In `load()`: on `!res.ok`, set `error` to a message ("Failed to load documents. Please try again.") instead of leaving `docs` as `[]` silently.
- Render error banner above the table when `error` is set; clear it on successful reload.

---

## Scope Exclusions

- No backfill of `content_hash` for existing documents — they keep `NULL` and are not deduplicated retroactively.
- Hash uniqueness is global across all assets. If the same file content is fetched for two different assets, the second attempt is treated as a duplicate and skipped. This is acceptable — EDGAR filings are asset-specific by nature.
- No UI to view or download the raw file from the Documents page (existing "Open" link in `DocumentsList` component handles that for the analysis view).

---

## Files to Create / Modify

| File | Change |
|------|--------|
| `backend/alembic/versions/040_add_content_hash.py` | New migration: add `content_hash` column + partial unique index |
| `backend/app/models/document.py` | Add `content_hash` field |
| `backend/app/services/document_manager.py` | Hash + dedup logic in `pre_fetch()` |
| `backend/app/api/documents.py` | Hash check + 409 response + replace logic in upload endpoint |
| `frontend/app/(auth)/documents/page.tsx` | Duplicate warning modal + error state |
