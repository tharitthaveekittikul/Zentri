# Platform Badge with Per-User Color Config

**Date:** 2026-05-08  
**Status:** Approved

## Overview

Add a colored pill badge inline after each ticker symbol in the portfolio holdings table, showing which platform the holding belongs to. Each user can customize the color of each platform from the settings page. Colors are stored in the database and included in backup/restore.

## Backend

### New Model: `PlatformConfig`

File: `backend/app/models/platform_config.py`

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID FK → `users` | cascade delete |
| `name` | String(100) | platform name |
| `color` | String(7) | hex color e.g. `#FF6B00` |

Unique constraint on `(user_id, name)`.

### Alembic Migration

Create table `platform_configs` with the fields above.

### New API Router: `backend/app/api/platforms.py`

Registered at `/api/v1/platforms`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/platforms` | Return all `{name, color}` configs for current user |
| `PUT` | `/api/v1/platforms/{name}` | Upsert color for a platform (body: `{color: string}`) |
| `DELETE` | `/api/v1/platforms/{name}` | Remove color config for a platform |

### Backup Changes

Files: `backend/app/schemas/system_backup.py`, `backend/app/services/system_backup.py`

- Add `BackupPlatformConfig(name: str, color: str)` Pydantic model to schema
- Add `platform_configs: list[BackupPlatformConfig] = []` field to `SystemBackup`
- Bump `version` default from `"2"` to `"3"`
- Add `"3"` to `SUPPORTED_VERSIONS` (keep `"1"`, `"2"` for backward compat — they import with empty platform_configs)
- `export_backup`: query all `PlatformConfig` rows for the user and populate the field
- `import_backup`: upsert each `BackupPlatformConfig` into `platform_configs` table

## Frontend

### New Service

File: `frontend/lib/services/platform-configs.ts`

- `fetchPlatformConfigs(): Promise<PlatformConfig[]>` — `GET /api/v1/platforms`
- `updatePlatformColor(name: string, color: string): Promise<void>` — `PUT /api/v1/platforms/{name}`
- `deletePlatformColor(name: string): Promise<void>` — `DELETE /api/v1/platforms/{name}`

### Portfolio Page (`frontend/app/(auth)/portfolio/page.tsx`)

- Add `useQuery` for platform configs (`queryKey: ["platform-configs"]`)
- Build `platformColors: Record<string, string>` map from the result
- Pass `platformColors` as a new prop to `HoldingsTable`

### Holdings Table (`frontend/components/portfolio/HoldingsTable.tsx`)

- Accept new prop `platformColors: Record<string, string>`
- In the `symbol` column cell (after the symbol text), render a pill badge when `row.original.platform` is set:
  - Background: `platformColors[platform]` if configured, else neutral muted (`bg-muted text-muted-foreground`)
  - Text color: auto-contrast — white (`#ffffff`) or black (`#000000`) based on relative luminance of background hex
  - Badge text: platform name, truncated at ~16 chars
  - Size: `text-[10px] px-1.5 py-0.5 rounded-full font-medium`

### Settings Page (`frontend/app/(auth)/settings/page.tsx`)

Add a new "Platforms" section:

- Fetch platform configs + all holdings (to derive unique platform names in use)
- For each unique platform name from holdings:
  - Show platform name label
  - Show `<input type="color">` initialized to configured color (or a sensible default if not yet set)
  - On change: call `updatePlatformColor(name, color)` and invalidate `["platform-configs"]` query
- If a platform has no holdings (orphaned config), still show it with a delete button

## Error Handling

- `PUT` with invalid hex (not matching `^#[0-9a-fA-F]{6}$`) → backend returns 422
- Platform name not found on `DELETE` → return 404
- Frontend color picker always produces valid hex — no frontend validation needed

## Backward Compatibility

- Backup versions `"1"` and `"2"` import without `platform_configs` — field defaults to `[]`, no configs are imported, which is correct
- Holdings without a platform (`platform: null`) show no badge — no change to existing behavior
