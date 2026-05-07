# Price Schedule Config + Pipeline Triggers — Design Spec

**Date:** 2026-05-07  
**Status:** Approved

---

## Overview

Add dynamic price fetch scheduling and manual pipeline triggers. Users configure each job's enable/disable, run time (Bangkok timezone), and days of week from a new Settings "Schedule" tab. Schedule settings are persisted in DB, included in backup/restore. All 6 jobs gain a manual trigger button on the Pipeline page.

---

## Defaults

| Job Key | Days | Start Hour (Bangkok) | Pattern |
|---------|------|----------------------|---------|
| `us_stock` | Mon–Fri | 19:00 | every 15 min from start hour |
| `thai_stock` | Mon–Fri | 13:00 | once daily |
| `thai_fund` | Mon–Fri | 13:00 | once daily |
| `crypto` | Every day | 00:00 | every 15 min all day |
| `gold` | Every day | 00:00 | every 15 min all day |
| `benchmark` | Every day | 00:00 | once daily (midnight UTC) |

Days stored as JSON array of integers: 0=Mon, 1=Tue, …, 6=Sun.

---

## Section 1 — Database

### New table: `price_schedule_config`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users, ON DELETE CASCADE |
| `job_key` | VARCHAR(50) | One of the 6 job keys above |
| `enabled` | BOOLEAN | Default true |
| `days` | JSON | Array of ints, e.g. `[0,1,2,3,4]` |
| `run_at_hour` | INT | Bangkok hour 0–23 |
| `run_at_minute` | INT | 0–59, default 0 |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

Unique constraint: `(user_id, job_key)`.

Seeded with defaults on first `GET /settings/schedule` if rows are missing.

---

## Section 2 — Backend: Worker Guard

### Cron changes in `worker/main.py`

- **Interval jobs** (`us_stock`, `crypto`, `gold`): cron stays at `minute={0, 15, 30, 45}`. No hour/day constraint in cron definition — guard handles it.
- **Once-daily jobs** (`thai_stock`, `thai_fund`, `benchmark`): cron changes from fixed `hour=X` to `minute=0` (fires every hour at :00). Guard selects the right hour.

### Guard logic (runs inside each job function, before any work)

Price fetch jobs run globally (not per-user), so the guard reads from the **first registered user's** schedule config (lowest `created_at`). This matches Zentri's single-user assumption. If no config row exists for that user, defaults apply.

```python
async def _should_run(db, job_key, pattern) -> bool:
    config = await get_schedule_config_for_primary_user(db, job_key)  # returns defaults if missing
    if not config.enabled:
        return False
    now_bkk = datetime.now(ZoneInfo("Asia/Bangkok"))
    if now_bkk.weekday() not in config.days:  # weekday(): 0=Mon
        return False
    if pattern == "once_daily":
        return now_bkk.hour == config.run_at_hour
    if pattern == "interval":
        return now_bkk.hour >= config.run_at_hour
    return True
```

**Manual trigger bypasses guard entirely** — enqueued jobs always execute.

---

## Section 3 — Backend: APIs

### New settings endpoint

```
GET  /api/v1/settings/schedule         → list[ScheduleConfigOut]
PUT  /api/v1/settings/schedule         → bulk upsert all 6 configs → list[ScheduleConfigOut]
```

Schema `ScheduleConfigOut / ScheduleConfigIn`:
```python
class ScheduleConfigOut(BaseModel):
    job_key: str
    enabled: bool
    days: list[int]      # 0–6
    run_at_hour: int
    run_at_minute: int
```

### New pipeline trigger endpoint

```
POST /api/v1/pipeline/trigger/{job_key}   → {"ok": true, "job_id": "..."}
```

Enqueues the named ARQ job immediately. Returns 400 for unknown `job_key`. No guard check — always runs.

Valid `job_key` values: `us_stock`, `thai_stock`, `thai_fund`, `crypto`, `gold`, `benchmark`.

---

## Section 4 — Backup

### Schema change

`BackupSettings` gains:
```python
schedule_configs: list[BackupScheduleConfig] = []
```

```python
class BackupScheduleConfig(BaseModel):
    job_key: str
    enabled: bool
    days: list[int]
    run_at_hour: int
    run_at_minute: int
```

### Version bump

Backup version: `"1"` → `"2"`.

`SUPPORTED_VERSIONS = {"1", "2"}`.

`import_backup` behavior:
- v2: restores `schedule_configs` via upsert.
- v1: skips schedule restore; DB defaults apply.

`export_backup` always writes v2 with full `schedule_configs`.

---

## Section 5 — Frontend

### Pipeline page (`/pipeline`)

Add a **Trigger Jobs** section above the jobs table:

- 6 buttons: US Stock, Thai Stock/DR, Thai Fund, Crypto, Gold, Benchmark
- Each button: shows job label, calls `POST /api/v1/pipeline/trigger/{job_key}`
- State per button: idle → loading spinner → success toast / error toast
- Buttons are independent (one loading doesn't block others)

### Settings page — new "Schedule" tab

5th tab added: **Schedule** (after Notifications).

Tab content — one card per job (6 cards total), each card has:

1. **Header row**: Job display name + enable/disable toggle (right-aligned)
2. **Time row**: Hour:Minute picker (Bangkok time label shown)
3. **Days row**: 7 checkboxes (Mon Tue Wed Thu Fri Sat Sun)

One **Save Schedule** button at the bottom — bulk saves all 6 configs via `PUT /settings/schedule`.

Cards are always visible regardless of toggle state (so user can configure before enabling).

### Frontend service additions

New functions in `lib/services/`:
- `fetchScheduleConfigs()` → `GET /settings/schedule`
- `saveScheduleConfigs(configs)` → `PUT /settings/schedule`
- `triggerJob(jobKey)` → `POST /pipeline/trigger/{job_key}`

---

## Files to Create / Modify

### Backend
- `backend/app/models/price_schedule_config.py` — new SQLAlchemy model
- `backend/alembic/versions/xxxx_add_price_schedule_config.py` — new migration
- `backend/app/schemas/price_schedule_config.py` — Pydantic schemas
- `backend/app/services/price_schedule_config.py` — CRUD + default seeding
- `backend/app/api/settings.py` — add `GET/PUT /schedule` endpoints
- `backend/app/api/pipeline.py` — add `POST /trigger/{job_key}` endpoint
- `backend/worker/jobs/price_fetch.py` — add guard to each job function
- `backend/worker/main.py` — update once-daily cron to fire every hour
- `backend/app/schemas/system_backup.py` — add `BackupScheduleConfig`, update `BackupSettings`
- `backend/app/services/system_backup.py` — update export/import, bump version to "2"

### Frontend
- `frontend/lib/services/schedule.ts` — new service (fetchScheduleConfigs, saveScheduleConfigs)
- `frontend/lib/services/pipeline.ts` — add `triggerJob(jobKey)`
- `frontend/components/pipeline/TriggerButtons.tsx` — new component
- `frontend/app/(auth)/pipeline/page.tsx` — add TriggerButtons above JobsTable
- `frontend/components/settings/ScheduleTab.tsx` — new component
- `frontend/app/(auth)/settings/page.tsx` — add Schedule tab

---

## Error Handling

- `POST /trigger/{job_key}` with unknown key → HTTP 400
- `PUT /settings/schedule` with invalid hours/days → HTTP 422 (Pydantic validation)
- Worker guard DB failure → log error, default to skip (safe fail)
- Frontend trigger button: toast error on non-2xx; button returns to idle state

---

## Out of Scope

- Per-job interval configuration (15 min is hardcoded for interval jobs)
- End-time / market-close cutoff for interval jobs
- Multi-user schedule isolation (each user has their own config, but worker runs globally — single-user assumption)
