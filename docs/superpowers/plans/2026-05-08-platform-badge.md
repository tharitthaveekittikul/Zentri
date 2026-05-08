# Platform Badge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a colored pill badge inline next to each ticker symbol in the portfolio holdings table, with per-user platform colors stored in the DB and customizable from the settings page.

**Architecture:** New `platform_configs` table (per-user, keyed by platform name string) backed by a FastAPI router at `/api/v1/platforms`. Frontend fetches colors as a separate query and passes a `Record<string, string>` map to the holdings table for badge rendering. Backup/restore includes platform configs in a new version `"3"` backup.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), Next.js/React Query/Tailwind (frontend), Alembic (migrations), pytest-asyncio (backend tests)

---

## File Map

| Action | File |
|--------|------|
| Create | `backend/app/models/platform_config.py` |
| Modify | `backend/app/models/__init__.py` |
| Create | `backend/alembic/versions/031_add_platform_configs.py` |
| Create | `backend/app/api/platforms.py` |
| Modify | `backend/app/main.py` |
| Create | `backend/tests/test_platforms.py` |
| Modify | `backend/app/schemas/system_backup.py` |
| Modify | `backend/app/services/system_backup.py` |
| Create | `frontend/lib/services/platform-configs.ts` |
| Modify | `frontend/components/portfolio/HoldingsTable.tsx` |
| Modify | `frontend/app/(auth)/portfolio/page.tsx` |
| Modify | `frontend/app/(auth)/settings/page.tsx` |

---

## Task 1: PlatformConfig model + migration

**Files:**
- Create: `backend/app/models/platform_config.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/031_add_platform_configs.py`

- [ ] **Step 1: Create the model**

Create `backend/app/models/platform_config.py`:

```python
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlatformConfig(Base):
    __tablename__ = "platform_configs"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_platform_configs_user_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
```

- [ ] **Step 2: Register in `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.platform_config import PlatformConfig  # noqa: F401
```

And add `"PlatformConfig"` to the `__all__` list.

- [ ] **Step 3: Write the migration**

Create `backend/alembic/versions/031_add_platform_configs.py`:

```python
"""add platform_configs table

Revision ID: 031
Revises: 030
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_platform_configs_user_name"),
    )
    op.create_index(op.f("ix_platform_configs_user_id"), "platform_configs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_platform_configs_user_id"), table_name="platform_configs")
    op.drop_table("platform_configs")
```

- [ ] **Step 4: Run migration**

```bash
cd backend && docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 030 -> 031, add platform_configs table`

---

## Task 2: Platforms API router

**Files:**
- Create: `backend/app/api/platforms.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_platforms.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_platforms.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_list_platforms_empty(auth_client):
    res = await auth_client.get("/api/v1/platforms")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_upsert_and_list_platform(auth_client):
    res = await auth_client.put("/api/v1/platforms/Bitkub", json={"color": "#FF6B00"})
    assert res.status_code == 200
    assert res.json() == {"ok": True}

    res = await auth_client.get("/api/v1/platforms")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "Bitkub"
    assert data[0]["color"] == "#FF6B00"


@pytest.mark.asyncio
async def test_upsert_updates_existing(auth_client):
    await auth_client.put("/api/v1/platforms/Bitkub", json={"color": "#FF6B00"})
    await auth_client.put("/api/v1/platforms/Bitkub", json={"color": "#123456"})

    res = await auth_client.get("/api/v1/platforms")
    data = res.json()
    assert len(data) == 1
    assert data[0]["color"] == "#123456"


@pytest.mark.asyncio
async def test_delete_platform(auth_client):
    await auth_client.put("/api/v1/platforms/Bitkub", json={"color": "#FF6B00"})
    res = await auth_client.delete("/api/v1/platforms/Bitkub")
    assert res.status_code == 204

    res = await auth_client.get("/api/v1/platforms")
    assert res.json() == []


@pytest.mark.asyncio
async def test_delete_platform_not_found(auth_client):
    res = await auth_client.delete("/api/v1/platforms/NoSuchPlatform")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_upsert_invalid_color(auth_client):
    res = await auth_client.put("/api/v1/platforms/Bitkub", json={"color": "red"})
    assert res.status_code == 422
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && docker compose exec backend pytest tests/test_platforms.py -v
```

Expected: all 6 tests FAIL (router doesn't exist yet)

- [ ] **Step 3: Create the router**

Create `backend/app/api/platforms.py`:

```python
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.platform_config import PlatformConfig
from app.models.user import User

router = APIRouter(prefix="/platforms", tags=["platforms"])
logger = get_logger(__name__)

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class PlatformColorIn(BaseModel):
    color: str

    @field_validator("color")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        if not HEX_RE.match(v):
            raise ValueError("color must be a 6-digit hex string like #FF6B00")
        return v


class PlatformConfigOut(BaseModel):
    name: str
    color: str


@router.get("", response_model=list[PlatformConfigOut])
async def list_platform_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PlatformConfig)
        .where(PlatformConfig.user_id == current_user.id)
        .order_by(PlatformConfig.name)
    )
    rows = result.scalars().all()
    return [PlatformConfigOut(name=r.name, color=r.color) for r in rows]


@router.put("/{name}")
async def upsert_platform_color(
    name: str,
    body: PlatformColorIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        insert(PlatformConfig)
        .values(id=uuid.uuid4(), user_id=current_user.id, name=name, color=body.color)
        .on_conflict_do_update(
            constraint="uq_platform_configs_user_name",
            set_={"color": body.color},
        )
    )
    await db.execute(stmt)
    await db.commit()
    logger.info("upserted platform color user=%s name=%s color=%s", current_user.id, name, body.color)
    return {"ok": True}


@router.delete("/{name}", status_code=204)
async def delete_platform_color(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        delete(PlatformConfig)
        .where(PlatformConfig.user_id == current_user.id, PlatformConfig.name == name)
        .returning(PlatformConfig.id)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Platform config not found")
    await db.commit()
```

- [ ] **Step 4: Register router in `backend/app/main.py`**

Add the import at the top with the other API imports:
```python
from app.api import platforms
```

Add the router registration after the last `include_router` line:
```python
app.include_router(platforms.router, prefix="/api/v1")
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
cd backend && docker compose exec backend pytest tests/test_platforms.py -v
```

Expected: all 6 tests PASS

---

## Task 3: Backup schema + service updates

**Files:**
- Modify: `backend/app/schemas/system_backup.py`
- Modify: `backend/app/services/system_backup.py`

- [ ] **Step 1: Add `BackupPlatformConfig` to schema and bump version**

In `backend/app/schemas/system_backup.py`, add this class after `BackupAIAnalysis`:

```python
class BackupPlatformConfig(BaseModel):
    name: str
    color: str
```

In the `SystemBackup` class, add the new field and update the version default:

```python
class SystemBackup(BaseModel):
    model_config = {"from_attributes": True}

    version: str = "3"          # was "2"
    exported_at: datetime
    settings: BackupSettings
    portfolio: BackupPortfolio
    provider_configs: list[BackupProviderConfig] = []
    feature_llm_configs: list[BackupFeatureLLMConfig] = []
    watchlist: list[BackupWatchlistItem] = []
    cash_balances: list[BackupCashBalance] = []
    ai_analyses: list[BackupAIAnalysis] = []
    platform_configs: list[BackupPlatformConfig] = []   # new field
```

- [ ] **Step 2: Update backup service — add version, imports, export, and import**

In `backend/app/services/system_backup.py`:

**a) Add `"3"` to supported versions and import the new model/schema:**

```python
SUPPORTED_VERSIONS = {"1", "2", "3"}
```

Add imports near the top of the file (with the other model imports):
```python
from app.models.platform_config import PlatformConfig
from app.schemas.system_backup import BackupPlatformConfig
```

**b) In `export_backup`, query platform configs and include them in the return value.** Add this block before the `return SystemBackup(...)` call at the end of the function:

```python
    # Platform configs
    pc_rows = await db.execute(
        select(PlatformConfig).where(PlatformConfig.user_id == user_id)
    )
    platform_configs = [
        BackupPlatformConfig(name=pc.name, color=pc.color)
        for pc in pc_rows.scalars().all()
    ]
```

Then add `platform_configs=platform_configs` to the `SystemBackup(...)` constructor call.

**c) In `import_backup`, delete existing platform configs and restore from backup.** Add this delete line in the wipe section (with the other deletes):

```python
    await db.execute(delete(PlatformConfig).where(PlatformConfig.user_id == user_id))
```

Add this restore block after the last restore section (before `await db.commit()`):

```python
    # Platform configs
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    for pc in backup.platform_configs:
        stmt = (
            pg_insert(PlatformConfig)
            .values(id=uuid.uuid4(), user_id=user_id, name=pc.name, color=pc.color)
            .on_conflict_do_update(
                constraint="uq_platform_configs_user_name",
                set_={"color": pc.color},
            )
        )
        await db.execute(stmt)
    logger.info("Restored %d platform configs", len(backup.platform_configs))
```

- [ ] **Step 3: Verify backup round-trip manually**

```bash
# Export
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/system/export | python3 -c "import sys,json; d=json.load(sys.stdin); print('version:', d['version'], 'platform_configs:', d['platform_configs'])"
```

Expected: `version: 3 platform_configs: [...]` (empty list if none configured yet)

---

## Task 4: Frontend platform-configs service

**Files:**
- Create: `frontend/lib/services/platform-configs.ts`

- [ ] **Step 1: Create the service**

Create `frontend/lib/services/platform-configs.ts`:

```typescript
import { api } from "@/lib/api";

export interface PlatformConfig {
  name: string;
  color: string;
}

export async function fetchPlatformConfigs(): Promise<PlatformConfig[]> {
  const res = await api.get("/api/v1/platforms");
  return res.json();
}

export async function updatePlatformColor(name: string, color: string): Promise<void> {
  await api.put(`/api/v1/platforms/${encodeURIComponent(name)}`, { json: { color } });
}

export async function deletePlatformColor(name: string): Promise<void> {
  await api.delete(`/api/v1/platforms/${encodeURIComponent(name)}`);
}
```

---

## Task 5: Platform badge in HoldingsTable

**Files:**
- Modify: `frontend/components/portfolio/HoldingsTable.tsx`

- [ ] **Step 1: Add `platformColors` prop and badge helper**

In `HoldingsTable.tsx`, update the `Props` interface to accept platform colors:

```typescript
interface Props {
  data: PaginatedResponse<HoldingRow>;
  params: TableParams;
  onParamChange: (updates: Record<string, string | number | null>, resetPage?: boolean) => void;
  onDelete: (id: string) => void;
  onUpdated: () => void;
  isFetching?: boolean;
  platformColors?: Record<string, string>;
}
```

Update the function signature to destructure `platformColors`:

```typescript
export function HoldingsTable({
  data,
  params,
  onParamChange,
  onDelete,
  onUpdated,
  isFetching = false,
  platformColors = {},
}: Props) {
```

Add this helper function inside the component (before the `columns` definition):

```typescript
  function contrastColor(hex: string): string {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const lin = (c: number) => {
      const s = c / 255;
      return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    };
    const L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    return L > 0.179 ? "#000000" : "#ffffff";
  }
```

- [ ] **Step 2: Render the badge in the symbol column cell**

Replace the `cell` of the `symbol` column (the `<div className="flex items-center gap-2">` block) with:

```typescript
      cell: ({ row }) => {
        const platform = row.original.platform;
        const bgColor = platform ? platformColors[platform] : undefined;
        return (
          <Link
            href={`/portfolio/${encodeURIComponent(row.original.symbol)}`}
            className="hover:underline"
            prefetch={false}
          >
            <div className="flex items-center gap-2 flex-wrap">
              <TickerLogo symbol={row.original.symbol} logoUrl={row.original.metadata_?.logo_url as string | undefined} />
              <span>{row.original.symbol}</span>
              {platform && (
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded-full font-medium max-w-[96px] truncate"
                  style={
                    bgColor
                      ? { backgroundColor: bgColor, color: contrastColor(bgColor) }
                      : undefined
                  }
                  // fallback when no color configured
                  data-no-color={!bgColor || undefined}
                >
                  {platform}
                </span>
              )}
            </div>
          </Link>
        );
      },
```

Add fallback styling for badges with no configured color by adding this to a `<style>` tag or via Tailwind — use a `data-no-color` attribute selector via inline className logic instead:

Replace the badge span with:

```typescript
              {platform && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium max-w-[96px] truncate ${
                    bgColor ? "" : "bg-muted text-muted-foreground"
                  }`}
                  style={
                    bgColor
                      ? { backgroundColor: bgColor, color: contrastColor(bgColor) }
                      : undefined
                  }
                >
                  {platform}
                </span>
              )}
```

---

## Task 6: Wire platformColors into portfolio page

**Files:**
- Modify: `frontend/app/(auth)/portfolio/page.tsx`

- [ ] **Step 1: Add import and query**

Add import at the top:
```typescript
import { fetchPlatformConfigs } from "@/lib/services/platform-configs";
```

Add this query inside `PortfolioPage` (alongside the other `useQuery` calls):
```typescript
  const { data: platformConfigsList } = useQuery({
    queryKey: ["platform-configs"],
    queryFn: fetchPlatformConfigs,
    initialData: [],
  });

  const platformColors = Object.fromEntries(
    platformConfigsList.map((pc) => [pc.name, pc.color])
  );
```

- [ ] **Step 2: Pass `platformColors` to `HoldingsTable`**

In the `<HoldingsTable ...>` JSX, add the new prop:
```typescript
          platformColors={platformColors}
```

---

## Task 7: Platforms tab in Settings page

**Files:**
- Modify: `frontend/app/(auth)/settings/page.tsx`

- [ ] **Step 1: Add imports**

Add these imports at the top of the settings page:
```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchPlatformConfigs, updatePlatformColor, type PlatformConfig } from "@/lib/services/platform-configs";
import { fetchHoldings } from "@/lib/services/portfolio";
```

- [ ] **Step 2: Add queries inside `SettingsPage`**

Add inside the `SettingsPage` component (near the top, with other state):
```typescript
  const qc = useQueryClient();

  const { data: platformConfigs = [] } = useQuery({
    queryKey: ["platform-configs"],
    queryFn: fetchPlatformConfigs,
  });

  const { data: holdingsPage } = useQuery({
    queryKey: ["holdings-all-settings"],
    queryFn: () => fetchHoldings({ page: 1, page_size: 1000 }),
  });

  const uniquePlatforms: string[] = Array.from(
    new Set(
      (holdingsPage?.items ?? [])
        .map((h) => h.platform)
        .filter((p): p is string => Boolean(p))
    )
  ).sort();

  const platformColorMap = Object.fromEntries(
    platformConfigs.map((pc) => [pc.name, pc.color])
  );

  const colorMutation = useMutation({
    mutationFn: ({ name, color }: { name: string; color: string }) =>
      updatePlatformColor(name, color),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["platform-configs"] }),
    onError: () => toast.error("Failed to save platform color"),
  });
```

- [ ] **Step 3: Add "Platforms" tab trigger**

In the `<TabsList>` block, add after the last `<TabsTrigger>`:
```typescript
          <TabsTrigger value="platforms">Platforms</TabsTrigger>
```

- [ ] **Step 4: Add `TabsContent` for Platforms**

Add after the last `</TabsContent>` closing tag (before `</Tabs>`):

```typescript
        <TabsContent value="platforms" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Platform Colors</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {uniquePlatforms.length === 0 ? (
                <p className="text-sm text-muted-foreground">No platforms found in your holdings.</p>
              ) : (
                uniquePlatforms.map((platform) => (
                  <div key={platform} className="flex items-center justify-between gap-4">
                    <span className="text-sm font-medium">{platform}</span>
                    <input
                      type="color"
                      value={platformColorMap[platform] ?? "#6366f1"}
                      className="h-8 w-16 cursor-pointer rounded border border-border bg-transparent p-0.5"
                      onChange={(e) =>
                        colorMutation.mutate({ name: platform, color: e.target.value })
                      }
                    />
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>
```

- [ ] **Step 5: Verify end-to-end in browser**

1. Go to `/settings` → "Platforms" tab — should list all unique platforms from holdings
2. Change a color — badge on portfolio page should update after navigating back
3. Go to `/portfolio` — badges appear next to ticker symbols with correct background + contrasting text
4. Export backup from `/settings` backup section — check the JSON has `platform_configs` array and `version: "3"`
