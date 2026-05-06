# Settings Page — Telegram & Privacy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add privacy mode (backend + UI toggle) and Telegram settings UI tab to the settings page.

**Architecture:** Add `privacy_mode` boolean to the `User` model via Alembic migration, expose it via two new endpoints in the existing `settings.py` router, then wire both the Privacy card and Telegram tab into the existing settings page component.

**Tech Stack:** FastAPI, SQLAlchemy (async), Alembic, Next.js App Router, shadcn/ui, Tailwind CSS

---

## File Map

| Action | File |
|--------|------|
| Modify | `backend/app/models/user.py` |
| Create | `backend/alembic/versions/020_add_privacy_mode_to_users.py` |
| Modify | `backend/app/api/settings.py` |
| Modify | `frontend/app/(auth)/settings/page.tsx` |

---

### Task 1: Add `privacy_mode` to User model

**Files:**
- Modify: `backend/app/models/user.py`

- [ ] **Step 1: Add the column to the User model**

Open `backend/app/models/user.py`. Add `Boolean` to the SQLAlchemy imports and append the new column at the end of the class:

```python
from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text

class User(Base):
    # ... existing fields unchanged ...
    telegram_bot_token: Mapped[str | None] = mapped_column(Text(), nullable=True, default=None)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    privacy_mode: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
```

- [ ] **Step 2: Verify the model file has no syntax errors**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri
docker compose exec backend python -c "from app.models.user import User; print('OK')"
```

Expected output: `OK`

---

### Task 2: Create Alembic migration

**Files:**
- Create: `backend/alembic/versions/020_add_privacy_mode_to_users.py`

- [ ] **Step 1: Create the migration file**

Create `backend/alembic/versions/020_add_privacy_mode_to_users.py`:

```python
"""add privacy_mode to users

Revision ID: 020
Revises: 019
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("privacy_mode", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("users", "privacy_mode")
```

- [ ] **Step 2: Run the migration**

```bash
docker compose exec backend alembic upgrade head
```

Expected output ends with: `Running upgrade 019 -> 020, add privacy_mode to users`

- [ ] **Step 3: Verify the column exists**

```bash
docker compose exec db psql -U zentri -d zentri -c "\d users" | grep privacy
```

Expected output: `privacy_mode | boolean | not null | false`

---

### Task 3: Add privacy endpoints to settings API

**Files:**
- Modify: `backend/app/api/settings.py`

- [ ] **Step 1: Add Pydantic schemas and two endpoints**

Open `backend/app/api/settings.py`. Add the following block after the existing Telegram endpoints (after line 252):

```python
class PrivacySettingsOut(BaseModel):
    privacy_mode: bool


class PrivacySettingsIn(BaseModel):
    privacy_mode: bool


@router.get("/privacy", response_model=PrivacySettingsOut)
async def get_privacy_settings(
    current_user: User = Depends(get_current_user),
):
    return PrivacySettingsOut(privacy_mode=current_user.privacy_mode)


@router.patch("/privacy", response_model=PrivacySettingsOut)
async def update_privacy_settings(
    body: PrivacySettingsIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.privacy_mode = body.privacy_mode
    await db.commit()
    await db.refresh(current_user)
    return PrivacySettingsOut(privacy_mode=current_user.privacy_mode)
```

- [ ] **Step 2: Verify endpoints load without error**

```bash
docker compose exec backend python -c "from app.api.settings import router; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Test GET endpoint manually**

```bash
# Get a token first (replace with your actual credentials)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8000/api/v1/settings/privacy \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected output: `{"privacy_mode": false}`

- [ ] **Step 4: Test PATCH endpoint manually**

```bash
curl -s -X PATCH http://localhost:8000/api/v1/settings/privacy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"privacy_mode": true}' | python3 -m json.tool
```

Expected output: `{"privacy_mode": true}`

---

### Task 4: Add Privacy card to General tab in settings UI

**Files:**
- Modify: `frontend/app/(auth)/settings/page.tsx`

- [ ] **Step 1: Add Switch component from shadcn/ui**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx shadcn@latest add switch
```

Expected: Switch component added to `components/ui/switch.tsx`

- [ ] **Step 2: Add privacy state and API wiring**

Open `frontend/app/(auth)/settings/page.tsx`. Add the import at the top with the other shadcn imports:

```typescript
import { Switch } from "@/components/ui/switch";
```

Add `privacyMode` state after the existing state declarations (after `const [planToAge, setPlanToAge] = useState("85")`):

```typescript
const [privacyMode, setPrivacyMode] = useState(false);
```

Add a new `useEffect` after the existing profile useEffect:

```typescript
useEffect(() => {
  api
    .get("/api/v1/settings/privacy")
    .then((r) => r.json())
    .then((d) => setPrivacyMode(d.privacy_mode))
    .catch(() => null);
}, []);
```

Add a handler function after `saveProfileSettings`:

```typescript
async function togglePrivacyMode(value: boolean) {
  setPrivacyMode(value);
  try {
    await api.patch("/api/v1/settings/privacy", { privacy_mode: value });
  } catch {
    setPrivacyMode(!value);
    toast.error("Failed to update privacy mode");
  }
}
```

- [ ] **Step 3: Add Privacy card to the General tab**

In the JSX, after the closing `</Card>` of the Profile card (before `</TabsContent>`), add:

```tsx
<Card>
  <CardHeader>
    <CardTitle>Privacy</CardTitle>
  </CardHeader>
  <CardContent>
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm font-medium">Privacy Mode</p>
        <p className="text-xs text-muted-foreground">
          Hide portfolio values across the app
        </p>
      </div>
      <Switch
        checked={privacyMode}
        onCheckedChange={togglePrivacyMode}
      />
    </div>
  </CardContent>
</Card>
```

- [ ] **Step 4: Verify the page compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 5: Open browser and verify**

Navigate to `http://localhost:3000/settings`. Confirm:
- Privacy card appears below Profile card in General tab
- Toggle starts in correct state (matches DB value)
- Toggling saves immediately (no Save button needed) and persists on refresh

---

### Task 5: Add Telegram tab to settings UI

**Files:**
- Modify: `frontend/app/(auth)/settings/page.tsx`

- [ ] **Step 1: Add Telegram state declarations**

In `frontend/app/(auth)/settings/page.tsx`, add state after the `privacyMode` state:

```typescript
const [telegramToken, setTelegramToken] = useState("");
const [telegramChatId, setTelegramChatId] = useState("");
const [telegramHasToken, setTelegramHasToken] = useState(false);
const [telegramTesting, setTelegramTesting] = useState(false);
```

- [ ] **Step 2: Add Telegram data fetch useEffect**

Add after the privacy useEffect:

```typescript
useEffect(() => {
  api
    .get("/api/v1/settings/telegram")
    .then((r) => r.json())
    .then((d) => {
      setTelegramChatId(d.chat_id ?? "");
      setTelegramHasToken(d.has_token);
    })
    .catch(() => null);
}, []);
```

- [ ] **Step 3: Add Telegram handler functions**

Add after `togglePrivacyMode`:

```typescript
async function saveTelegramConfig() {
  try {
    await api.put("/api/v1/settings/telegram", {
      bot_token: telegramToken,
      chat_id: telegramChatId,
    });
    setTelegramHasToken(true);
    setTelegramToken("");
    toast.success("Telegram config saved");
  } catch {
    toast.error("Failed to save Telegram config");
  }
}

async function testTelegram() {
  setTelegramTesting(true);
  try {
    await api.post("/api/v1/settings/telegram/test", {});
    toast.success("Test message sent — check your Telegram");
  } catch {
    toast.error("Telegram delivery failed — check your token and chat ID");
  } finally {
    setTelegramTesting(false);
  }
}
```

- [ ] **Step 4: Add Notifications tab trigger**

In the `<TabsList>` JSX, add after the AI trigger:

```tsx
<TabsTrigger value="notifications">Notifications</TabsTrigger>
```

- [ ] **Step 5: Add Notifications tab content**

After the closing `</TabsContent>` of the AI tab, add:

```tsx
<TabsContent value="notifications" className="space-y-6 mt-4">
  <Card>
    <CardHeader>
      <CardTitle>Telegram Alerts</CardTitle>
    </CardHeader>
    <CardContent className="space-y-4">
      <div className="space-y-3">
        <div>
          <label className="text-sm font-medium mb-1 block">Bot Token</label>
          <Input
            type="password"
            placeholder={telegramHasToken ? "••••••••" : "Enter bot token from @BotFather"}
            value={telegramToken}
            onChange={(e) => setTelegramToken(e.target.value)}
          />
        </div>
        <div>
          <label className="text-sm font-medium mb-1 block">Chat ID</label>
          <Input
            placeholder="e.g. 123456789"
            value={telegramChatId}
            onChange={(e) => setTelegramChatId(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <Button
            onClick={saveTelegramConfig}
            disabled={!telegramToken && !telegramChatId}
            className="hover:bg-primary/90 active:scale-95 transition-all cursor-pointer"
          >
            Save
          </Button>
          <Button
            variant="outline"
            onClick={testTelegram}
            disabled={telegramTesting || !telegramHasToken}
            className="active:scale-95 transition-all cursor-pointer"
          >
            {telegramTesting ? "Sending…" : "Send Test Message"}
          </Button>
        </div>
        {telegramHasToken && (
          <p className="text-xs text-muted-foreground">
            Bot token saved. Enter a new token to replace it.
          </p>
        )}
      </div>
    </CardContent>
  </Card>
</TabsContent>
```

- [ ] **Step 6: Verify the page compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 7: Open browser and verify Telegram tab**

Navigate to `http://localhost:3000/settings` → Notifications tab. Confirm:
- Bot Token field shows masked placeholder when token is already saved
- Chat ID pre-fills from DB
- Save button disabled when both fields are empty
- Test button disabled when no token saved
- Test button sends message and shows toast

---

## Self-Review

**Spec coverage:**
- ✅ `privacy_mode` column on User model — Task 1
- ✅ Alembic migration — Task 2
- ✅ `GET /settings/privacy` — Task 3
- ✅ `PATCH /settings/privacy` — Task 3
- ✅ Privacy card in General tab with toggle — Task 4
- ✅ Telegram tab with token/chat_id/save/test — Task 5
- ✅ Page loads privacy state from API on mount — Task 4
- ✅ Page loads Telegram state from API on mount — Task 5

**No placeholders:** All steps contain exact code and commands.

**Type consistency:** `privacy_mode` (snake_case) used consistently in backend; `privacyMode` (camelCase) used consistently in frontend state.
