# Watchlist ATH Drop Column & Alert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "ATH Drop %" column to the watchlist table and a per-item Telegram alert that fires when the drop from ATH (rolling 365-day max price from DB) exceeds the user's threshold.

**Architecture:** ATH is computed as `max(Price.close)` over 365 days from the existing `prices` table — same formula as `discover_top_down`. Two new nullable columns on `watchlist_items` store the alert threshold and last-fired timestamp. The existing `check_and_notify` alert job gains a second pass for ATH drop alerts.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, Alembic, React/Next.js, TypeScript, Telegram Bot API

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `backend/alembic/versions/047_add_ath_alert_to_watchlist.py` | Create | Migration: add `ath_alert_threshold` + `ath_alerted_at` to `watchlist_items` |
| `backend/app/models/watchlist_item.py` | Modify | Add 2 mapped columns |
| `backend/app/schemas/watchlist.py` | Modify | Add `ath_drop_pct`, `ath_alert_threshold`, `ath_alerted_at` to Out; add `ath_alert_threshold` to Update |
| `backend/app/api/watchlist.py` | Modify | Compute `ath_drop_pct` in `_item_to_out`; reset `ath_alerted_at` in `/rearm` |
| `backend/app/services/watchlist_alert.py` | Modify | Add `_fetch_ath_alert_rows`, `_format_ath_alert_message`, second pass in `check_and_notify` |
| `backend/tests/services/test_watchlist_alert.py` | Modify | Add tests for ATH drop alert logic |
| `frontend/lib/services/watchlist.ts` | Modify | Add `ath_drop_pct`, `ath_alert_threshold`, `ath_alerted_at` to types |
| `frontend/app/(auth)/watchlist/page.tsx` | Modify | Add ATH Drop column + EditItemDialog |

---

## Task 1: Database Migration

**Files:**
- Create: `backend/alembic/versions/047_add_ath_alert_to_watchlist.py`

- [ ] **Step 1: Create migration file**

```python
"""add ath alert columns to watchlist_items

Revision ID: 047
Revises: 046
Create Date: 2026-05-26
"""
import sqlalchemy as sa
from alembic import op

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "watchlist_items",
        sa.Column("ath_alert_threshold", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "watchlist_items",
        sa.Column("ath_alerted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("watchlist_items", "ath_alerted_at")
    op.drop_column("watchlist_items", "ath_alert_threshold")
```

- [ ] **Step 2: Apply migration**

```bash
cd backend
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 046 -> 047, add ath alert columns to watchlist_items`

---

## Task 2: Update WatchlistItem Model

**Files:**
- Modify: `backend/app/models/watchlist_item.py`

- [ ] **Step 1: Add 2 mapped columns**

Replace the full file content:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, Text, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    alert_enabled: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ath_alert_threshold: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    ath_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("user_id", "asset_id", name="uq_watchlist_user_asset"),
    )
```

---

## Task 3: Update Schemas

**Files:**
- Modify: `backend/app/schemas/watchlist.py`

- [ ] **Step 1: Add fields to `WatchlistItemOut` and `WatchlistItemUpdate`**

Replace the full file content:

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AssetSummary(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    currency: str
    asset_type: str
    metadata_: dict = {}
    model_config = ConfigDict(from_attributes=True)


class WatchlistItemCreate(BaseModel):
    asset_id: uuid.UUID
    target_price: Decimal | None = None
    currency: str = "USD"
    notes: str | None = None


class WatchlistItemUpdate(BaseModel):
    target_price: Decimal | None = None
    notes: str | None = None
    alert_enabled: bool | None = None
    ath_alert_threshold: Decimal | None = None


class WatchlistItemOut(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    target_price: Decimal | None
    currency: str
    notes: str | None
    alert_enabled: bool
    alerted_at: datetime | None
    ath_alert_threshold: Decimal | None
    ath_alerted_at: datetime | None
    created_at: datetime
    asset: AssetSummary
    current_price: Decimal | None
    pct_from_target: float | None
    ath_drop_pct: float | None
    last_verdict: str | None = None
    ai_suggested_price: Decimal | None = None
    last_scanned_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class WatchlistSuggestionOut(BaseModel):
    id: uuid.UUID
    symbol: str
    asset_id: uuid.UUID | None
    reasoning: str
    suggested_price: Decimal | None
    verdict: str
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

---

## Task 4: Compute `ath_drop_pct` in API + Fix `/rearm`

**Files:**
- Modify: `backend/app/api/watchlist.py`

- [ ] **Step 1: Add `timedelta` and `Decimal` to imports**

Find this line in `backend/app/api/watchlist.py`:
```python
from datetime import datetime, timezone
```
Replace with:
```python
from datetime import datetime, timedelta, timezone
from decimal import Decimal
```

- [ ] **Step 2: Add ATH computation to `_item_to_out`**

Find the `_item_to_out` function. After the block that computes `current_price` and `pct`, and before the `analysis` query, add:

```python
    ATH_WINDOW_DAYS = 365
    since_ath = datetime.now(timezone.utc) - timedelta(days=ATH_WINDOW_DAYS)
    ath_result = await db.execute(
        select(func.max(Price.close))
        .where(Price.asset_id == item.asset_id, Price.timestamp >= since_ath)
    )
    ath = ath_result.scalar()
    ath_drop_pct = None
    if ath and current_price:
        ath_drop_pct = float(
            (Decimal(str(ath)) - Decimal(str(current_price))) / Decimal(str(ath)) * 100
        )
```

- [ ] **Step 3: Pass new fields to `WatchlistItemOut` constructor**

In the `return WatchlistItemOut(...)` call at the end of `_item_to_out`, add these fields:

```python
        ath_alert_threshold=item.ath_alert_threshold,
        ath_alerted_at=item.ath_alerted_at,
        ath_drop_pct=ath_drop_pct,
```

- [ ] **Step 4: Reset `ath_alerted_at` in `/rearm` endpoint**

Find the `rearm_watchlist_item` endpoint. After `item.alerted_at = None`, add:

```python
    item.ath_alerted_at = None
```

- [ ] **Step 5: Handle `ath_alert_threshold` in PATCH endpoint**

Find the `update_watchlist_item` endpoint. After the `alert_enabled` block, add:

```python
    if "ath_alert_threshold" in body.model_fields_set:
        item.ath_alert_threshold = body.ath_alert_threshold
```

---

## Task 5: ATH Drop Alert Service

**Files:**
- Modify: `backend/app/services/watchlist_alert.py`

- [ ] **Step 1: Add imports**

At the top of `backend/app/services/watchlist_alert.py`, add to existing imports:

```python
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func
```

(Keep the existing imports, just add these. `func` may already be imported via sqlalchemy — check and add only what is missing.)

- [ ] **Step 2: Add `_fetch_ath_alert_rows` helper**

After the existing `_fetch_pending_rows` function, add:

```python
async def _fetch_ath_alert_rows(db: AsyncSession) -> list:
    """Return rows (WatchlistItem, Asset, Price, User) where ATH alert threshold is set and not yet fired."""
    latest_ts = (
        select(Price.asset_id, func.max(Price.timestamp).label("max_ts"))
        .group_by(Price.asset_id)
        .subquery("latest_ts")
    )
    stmt = (
        select(WatchlistItem, Asset, Price, User)
        .join(Asset, WatchlistItem.asset_id == Asset.id)
        .join(User, WatchlistItem.user_id == User.id)
        .outerjoin(latest_ts, WatchlistItem.asset_id == latest_ts.c.asset_id)
        .outerjoin(
            Price,
            and_(
                Price.asset_id == WatchlistItem.asset_id,
                Price.timestamp == latest_ts.c.max_ts,
            ),
        )
        .where(
            WatchlistItem.ath_alert_threshold.isnot(None),
            WatchlistItem.ath_alerted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    return result.all()
```

- [ ] **Step 3: Add `_format_ath_alert_message` helper**

After `_format_alert_message`, add:

```python
def _format_ath_alert_message(
    item: WatchlistItem, asset: Asset, price: Price, ath_drop_pct: float
) -> str:
    return (
        f"📉 <b>ATH Drop Alert — {asset.symbol}</b>\n"
        f"{asset.name}\n\n"
        f"Dropped <b>-{ath_drop_pct:.1f}%</b> from ATH "
        f"(your threshold: {float(item.ath_alert_threshold):.0f}%)\n"
        f"Current price: <b>{price.close:.4f} {asset.currency}</b>\n\n"
        f"Open Zentri to review."
    )
```

- [ ] **Step 4: Add ATH drop pass to `check_and_notify`**

At the end of the existing `check_and_notify` function (after the existing `return count`), replace the final `return count` with:

```python
    # ATH drop alert pass
    ath_rows = await _fetch_ath_alert_rows(db)
    ATH_WINDOW_DAYS = 365
    since = datetime.now(timezone.utc) - timedelta(days=ATH_WINDOW_DAYS)
    for item, asset, price, user in ath_rows:
        if price is None:
            continue
        if not user.telegram_bot_token or not user.telegram_chat_id:
            logger.info("No Telegram config for user %s — skipping ATH alert", user.id)
            continue
        try:
            ath_result = await db.execute(
                select(func.max(Price.close))
                .where(Price.asset_id == item.asset_id, Price.timestamp >= since)
            )
            ath = ath_result.scalar()
            if not ath:
                continue
            ath_drop_pct = float(
                (Decimal(str(ath)) - Decimal(str(price.close))) / Decimal(str(ath)) * 100
            )
            if ath_drop_pct < float(item.ath_alert_threshold):
                continue
            bot_token = decrypt(user.telegram_bot_token)
            text = _format_ath_alert_message(item, asset, price, ath_drop_pct)
            await send_message(bot_token, user.telegram_chat_id, text)
            item.ath_alerted_at = datetime.now(timezone.utc)
            await db.commit()
            count += 1
            logger.info("ATH drop alert sent for %s (item %s) drop=%.1f%%", asset.symbol, item.id, ath_drop_pct)
        except Exception:
            logger.exception("Failed to send ATH alert for item %s (asset %s)", item.id, asset.symbol)

    return count
```

---

## Task 6: Tests for ATH Alert Service

**Files:**
- Modify: `backend/tests/services/test_watchlist_alert.py`

- [ ] **Step 1: Write failing tests**

Add the following tests to the end of `backend/tests/services/test_watchlist_alert.py`:

```python
def _ath_item(ath_alert_threshold=Decimal("20"), ath_alerted_at=None):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.ath_alert_threshold = ath_alert_threshold
    m.ath_alerted_at = ath_alerted_at
    m.asset_id = uuid.uuid4()
    return m


@pytest.mark.asyncio
async def test_ath_alert_sent_when_drop_exceeds_threshold():
    """ATH drop >= threshold → alert fires, ath_alerted_at set."""
    item = _ath_item(ath_alert_threshold=Decimal("20"))
    mock_db = AsyncMock()
    # max(Price.close) = 100, current close = 75 → drop = 25%
    mock_db.execute.return_value.scalar.return_value = Decimal("100")

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=[]):
        with patch("app.services.watchlist_alert._fetch_ath_alert_rows",
                   return_value=[(item, _asset(), _price(close=Decimal("75")), _user())]):
            with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock):
                count = await check_and_notify(mock_db)

    assert count == 1
    assert item.ath_alerted_at is not None


@pytest.mark.asyncio
async def test_ath_alert_not_sent_when_drop_below_threshold():
    """ATH drop < threshold → no alert."""
    item = _ath_item(ath_alert_threshold=Decimal("20"))
    mock_db = AsyncMock()
    # max(Price.close) = 100, current close = 90 → drop = 10%
    mock_db.execute.return_value.scalar.return_value = Decimal("100")

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=[]):
        with patch("app.services.watchlist_alert._fetch_ath_alert_rows",
                   return_value=[(item, _asset(), _price(close=Decimal("90")), _user())]):
            with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock) as mock_send:
                count = await check_and_notify(mock_db)

    assert count == 0
    assert item.ath_alerted_at is None
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_ath_alert_not_sent_when_no_price_history():
    """No ATH data (no prices in window) → skip."""
    item = _ath_item(ath_alert_threshold=Decimal("20"))
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalar.return_value = None  # no ATH

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=[]):
        with patch("app.services.watchlist_alert._fetch_ath_alert_rows",
                   return_value=[(item, _asset(), _price(close=Decimal("80")), _user())]):
            with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock) as mock_send:
                count = await check_and_notify(mock_db)

    assert count == 0
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_ath_alert_not_sent_when_no_telegram():
    """No Telegram config → skip ATH alert."""
    item = _ath_item(ath_alert_threshold=Decimal("20"))
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalar.return_value = Decimal("100")

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=[]):
        with patch("app.services.watchlist_alert._fetch_ath_alert_rows",
                   return_value=[(item, _asset(), _price(close=Decimal("75")), _user(has_telegram=False))]):
            with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock) as mock_send:
                count = await check_and_notify(mock_db)

    assert count == 0
    mock_send.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
docker compose exec backend pytest tests/services/test_watchlist_alert.py -v -k "ath"
```

Expected: 4 failures — `_fetch_ath_alert_rows` does not exist yet

- [ ] **Step 3: Run tests after implementing Task 5**

```bash
cd backend
docker compose exec backend pytest tests/services/test_watchlist_alert.py -v
```

Expected: all tests pass

---

## Task 7: Frontend — Types

**Files:**
- Modify: `frontend/lib/services/watchlist.ts`

- [ ] **Step 1: Add new fields to `WatchlistItem` interface**

Find the `WatchlistItem` interface and add 3 fields after `last_scanned_at`:

```ts
export interface WatchlistItem {
  id: string;
  asset_id: string;
  target_price: string | null;
  currency: string;
  notes: string | null;
  alert_enabled: boolean;
  alerted_at: string | null;
  created_at: string;
  asset: WatchlistAsset;
  current_price: string | null;
  pct_from_target: number | null;
  last_verdict: "BUY" | "SELL" | "HOLD" | null;
  ai_suggested_price: string | null;
  last_scanned_at: string | null;
  ath_drop_pct: number | null;
  ath_alert_threshold: string | null;
  ath_alerted_at: string | null;
}
```

- [ ] **Step 2: Add `ath_alert_threshold` to `updateWatchlistItem` patch type**

Find the `updateWatchlistItem` function signature. Replace its `patch` parameter type:

```ts
export async function updateWatchlistItem(
  id: string,
  patch: {
    target_price?: string | null;
    notes?: string | null;
    alert_enabled?: boolean;
    ath_alert_threshold?: string | null;
  },
): Promise<WatchlistItem> {
```

---

## Task 8: Frontend — ATH Drop Column

**Files:**
- Modify: `frontend/app/(auth)/watchlist/page.tsx`

- [ ] **Step 1: Add `Pencil` to lucide imports**

Find the lucide-react import line. Add `Pencil` to the list:

```ts
import {
  Bell,
  BellOff,
  Check,
  Pencil,
  Plus,
  Scan,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
```

- [ ] **Step 2: Add ATH drop color helper function**

Add this function near the top of the file, after the `VERDICT_STYLE` constant:

```ts
function athDropColor(pct: number | null, threshold: string | null): string {
  if (pct === null) return "text-muted-foreground";
  if (threshold !== null && pct >= parseFloat(threshold)) return "text-[var(--color-loss)]";
  if (pct >= 20) return "text-[var(--color-loss)]";
  if (pct >= 10) return "text-yellow-600 dark:text-yellow-400";
  return "text-muted-foreground";
}
```

- [ ] **Step 3: Add ATH Drop table header**

Find the `<TableHead>` block inside the watchlist table header row. After the `% From Target` header and before `Verdict`, add:

```tsx
<TableHead className="hidden md:table-cell text-right">ATH Drop</TableHead>
```

- [ ] **Step 4: Add `onEdit` prop to `WatchlistRow`**

Find the `WatchlistRow` props type. Add `onEdit`:

```ts
}: {
  item: WatchlistItem;
  formatNative: (value: string | number, nativeCurrency: string) => DualValue;
  scanningId: string | null;
  onScan: (id: string) => void;
  onApplyPrice: (item: WatchlistItem) => void;
  onToggleAlert: (item: WatchlistItem) => void;
  onEdit: (item: WatchlistItem) => void;
  onDelete: (id: string) => void;
}
```

- [ ] **Step 5: Add ATH Drop cell to `WatchlistRow` return**

Find the `% From Target` `<TableCell>` block in `WatchlistRow`. After it, add:

```tsx
      <TableCell className="hidden md:table-cell text-right">
        {item.ath_drop_pct !== null ? (
          <span className={athDropColor(item.ath_drop_pct, item.ath_alert_threshold)}>
            -{item.ath_drop_pct.toFixed(1)}%
            {item.ath_alerted_at && (
              <Bell className="inline ml-1 h-3 w-3" />
            )}
          </span>
        ) : (
          "—"
        )}
      </TableCell>
```

- [ ] **Step 6: Add Edit button to `WatchlistRow` actions**

In the `WatchlistRow` Actions `<div>`, add a pencil button before the Bell button:

```tsx
          <Button
            variant="ghost"
            size="icon"
            title="Edit"
            onClick={() => onEdit(item)}
          >
            <Pencil className="h-4 w-4" />
          </Button>
```

---

## Task 9: Frontend — EditItemDialog

**Files:**
- Modify: `frontend/app/(auth)/watchlist/page.tsx`

- [ ] **Step 1: Add `EditItemDialog` component**

Add this component function after the `AddWatchlistDialog` function and before `WatchlistRow`:

```tsx
function EditItemDialog({
  item,
  open,
  onClose,
  onSaved,
}: {
  item: WatchlistItem | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [targetPrice, setTargetPrice] = useState("");
  const [athThreshold, setAthThreshold] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (item) {
      setTargetPrice(item.target_price ?? "");
      setAthThreshold(item.ath_alert_threshold ?? "");
    }
  }, [item]);

  const handleSave = async () => {
    if (!item) return;
    setSaving(true);
    try {
      await updateWatchlistItem(item.id, {
        target_price: targetPrice || null,
        ath_alert_threshold: athThreshold || null,
      });
      toast.success("Saved");
      onSaved();
      onClose();
    } catch {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit {item?.asset.symbol}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">
              Target price (optional)
            </label>
            <Input
              type="number"
              placeholder="e.g. 150.00"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">
              ATH drop alert threshold % (optional, e.g. 20 = alert when down 20% from ATH)
            </label>
            <Input
              type="number"
              placeholder="e.g. 20"
              value={athThreshold}
              onChange={(e) => setAthThreshold(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Add `editItem` state to `WatchlistPage`**

In `WatchlistPage`, find the state declarations block. Add:

```ts
  const [editItem, setEditItem] = useState<WatchlistItem | null>(null);
```

- [ ] **Step 3: Add `handleEdit` handler**

After the `handleToggleAlert` function in `WatchlistPage`, add:

```ts
  const handleEdit = (item: WatchlistItem) => {
    setEditItem(item);
  };
```

- [ ] **Step 4: Wire `onEdit` into `WatchlistRow` calls**

Find all `<WatchlistRow` JSX elements. Add `onEdit={handleEdit}`:

```tsx
<WatchlistRow
  key={item.id}
  item={item}
  formatNative={formatNative}
  scanningId={scanningId}
  onScan={handleScanItem}
  onApplyPrice={handleApplyPrice}
  onToggleAlert={handleToggleAlert}
  onEdit={handleEdit}
  onDelete={handleDelete}
/>
```

- [ ] **Step 5: Render `EditItemDialog`**

Find where `<AddWatchlistDialog` is rendered in the JSX. Right after it, add:

```tsx
      <EditItemDialog
        item={editItem}
        open={editItem !== null}
        onClose={() => setEditItem(null)}
        onSaved={fetchAll}
      />
```

- [ ] **Step 6: TypeScript check**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors

---

## Task 10: Smoke Test (Manual)

- [ ] Open the watchlist page — verify ATH Drop column appears
- [ ] Click the pencil icon on a watchlist item — verify EditItemDialog opens with pre-filled values
- [ ] Set ATH threshold to `0.1` (0.1% → will trigger immediately for any stock) and save
- [ ] Verify the cell shows a percentage and turns red
- [ ] Reset threshold to a realistic value (e.g. `20`) and save
- [ ] Verify the Telegram alert job: `docker compose exec backend python -c "import asyncio; from app.services.watchlist_alert import check_and_notify; ..."` — or wait for the next scheduled job run
