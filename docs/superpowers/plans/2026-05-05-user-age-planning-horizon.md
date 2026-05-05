# User Age & Planning Horizon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional `birth_date` + `plan_to_age` to the user profile, expose them in the setup wizard and settings page, and inject age context into LLM prompts.

**Architecture:** Two nullable columns on `users` table. A `get_user_age_context()` helper derives current age and years remaining at runtime — never stored. The helper is called by any service building LLM prompts. Frontend gains a new setup wizard step and a Profile card in Settings.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), Next.js/TypeScript/Tailwind/shadcn (frontend), Alembic (migrations), pytest (tests)

---

## File Map

| Action | File |
|---|---|
| Create | `backend/alembic/versions/011_user_age_planning.py` |
| Modify | `backend/app/models/user.py` |
| Modify | `backend/app/schemas/auth.py` |
| Modify | `backend/app/api/settings.py` |
| Create | `backend/app/services/user_context.py` |
| Modify | `backend/app/services/overview.py` |
| Create | `backend/tests/test_user_age_context.py` |
| Modify | `frontend/lib/services/auth.ts` |
| Modify | `frontend/app/setup/page.tsx` |
| Modify | `frontend/app/(auth)/settings/page.tsx` |

---

## Task 1: Alembic migration — add `birth_date` + `plan_to_age`

**Files:**
- Create: `backend/alembic/versions/011_user_age_planning.py`

- [ ] **Step 1: Create migration file**

```python
# backend/alembic/versions/011_user_age_planning.py
"""add birth_date and plan_to_age to users

Revision ID: 011
Revises: 010
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("plan_to_age", sa.Integer(), nullable=True, server_default="85"))


def downgrade() -> None:
    op.drop_column("users", "plan_to_age")
    op.drop_column("users", "birth_date")
```

- [ ] **Step 2: Run migration**

```bash
cd backend
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 010 -> 011, add birth_date and plan_to_age to users`

---

## Task 2: Update `User` model

**Files:**
- Modify: `backend/app/models/user.py`

- [ ] **Step 1: Add fields to User model**

Replace the file content with:

```python
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    currency_primary: Mapped[str] = mapped_column(String(10), nullable=False, default="THB")
    currency_secondary: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    birth_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True, default=None)
    plan_to_age: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True, server_default="85")
```

- [ ] **Step 2: Verify the app starts without errors**

```bash
docker compose exec backend python -c "from app.models.user import User; print('OK')"
```

Expected: `OK`

---

## Task 3: Age context helper + tests (TDD)

**Files:**
- Create: `backend/tests/test_user_age_context.py`
- Create: `backend/app/services/user_context.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_user_age_context.py
from datetime import date
from unittest.mock import patch

import pytest

from app.services.user_context import get_user_age_context


class FakeUser:
    def __init__(self, birth_date, plan_to_age):
        self.birth_date = birth_date
        self.plan_to_age = plan_to_age


def test_returns_none_when_no_birth_date():
    user = FakeUser(birth_date=None, plan_to_age=85)
    assert get_user_age_context(user) is None


def test_returns_none_when_plan_to_age_missing():
    user = FakeUser(birth_date=date(1990, 1, 1), plan_to_age=None)
    assert get_user_age_context(user) is None


def test_computes_age_correctly():
    with patch("app.services.user_context.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 5)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        user = FakeUser(birth_date=date(1994, 3, 10), plan_to_age=85)
        ctx = get_user_age_context(user)
    assert ctx["current_age"] == 32
    assert ctx["plan_to_age"] == 85
    assert ctx["years_remaining"] == 53
    assert ctx["target_year"] == 2079


def test_birthday_not_yet_this_year():
    with patch("app.services.user_context.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 5)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        user = FakeUser(birth_date=date(1994, 12, 1), plan_to_age=85)
        ctx = get_user_age_context(user)
    assert ctx["current_age"] == 31


def test_prompt_string_format():
    with patch("app.services.user_context.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 5)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        user = FakeUser(birth_date=date(1994, 3, 10), plan_to_age=85)
        ctx = get_user_age_context(user)
    assert ctx["prompt"] == "User context: age 32, planning horizon until age 85 (53 years remaining)."
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd backend
docker compose exec backend python -m pytest tests/test_user_age_context.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.user_context'`

- [ ] **Step 3: Implement the helper**

```python
# backend/app/services/user_context.py
import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


def get_user_age_context(user: Any) -> dict | None:
    if not user.birth_date or user.plan_to_age is None:
        return None

    today = date.today()
    had_birthday = (today.month, today.day) >= (user.birth_date.month, user.birth_date.day)
    current_age = today.year - user.birth_date.year - (0 if had_birthday else 1)
    target_year = user.birth_date.year + user.plan_to_age
    years_remaining = target_year - today.year

    logger.debug("User age context: age=%d plan_to_age=%d", current_age, user.plan_to_age)

    return {
        "current_age": current_age,
        "plan_to_age": user.plan_to_age,
        "years_remaining": years_remaining,
        "target_year": target_year,
        "prompt": (
            f"User context: age {current_age}, planning horizon until age "
            f"{user.plan_to_age} ({years_remaining} years remaining)."
        ),
    }
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
docker compose exec backend python -m pytest tests/test_user_age_context.py -v
```

Expected: `5 passed`

---

## Task 4: Settings API — profile endpoint

**Files:**
- Modify: `backend/app/api/settings.py`

Add two new Pydantic models and two new routes (`GET /settings/profile`, `PATCH /settings/profile`) following the exact same pattern as the existing `DisplaySettingsIn/Out` and `/display` endpoint.

- [ ] **Step 1: Add profile models and routes to `backend/app/api/settings.py`**

Add these at the end of the file (before any `__all__` if present, otherwise just append):

```python
from datetime import date as date_type
from app.services.user_context import get_user_age_context


class ProfileSettingsIn(BaseModel):
    birth_date: date_type | None = None
    plan_to_age: int | None = None


class ProfileSettingsOut(BaseModel):
    birth_date: date_type | None
    plan_to_age: int | None
    current_age: int | None
    years_remaining: int | None
    target_year: int | None


@router.get("/profile", response_model=ProfileSettingsOut)
async def get_profile_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctx = get_user_age_context(current_user)
    return ProfileSettingsOut(
        birth_date=current_user.birth_date,
        plan_to_age=current_user.plan_to_age,
        current_age=ctx["current_age"] if ctx else None,
        years_remaining=ctx["years_remaining"] if ctx else None,
        target_year=ctx["target_year"] if ctx else None,
    )


@router.patch("/profile", response_model=ProfileSettingsOut)
async def update_profile_settings(
    body: ProfileSettingsIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.birth_date is not None or body.birth_date == None and "birth_date" in body.model_fields_set:
        current_user.birth_date = body.birth_date
    if body.plan_to_age is not None:
        current_user.plan_to_age = body.plan_to_age
    await db.commit()
    await db.refresh(current_user)
    ctx = get_user_age_context(current_user)
    return ProfileSettingsOut(
        birth_date=current_user.birth_date,
        plan_to_age=current_user.plan_to_age,
        current_age=ctx["current_age"] if ctx else None,
        years_remaining=ctx["years_remaining"] if ctx else None,
        target_year=ctx["target_year"] if ctx else None,
    )
```

- [ ] **Step 2: Verify routes appear in FastAPI docs**

```bash
docker compose exec backend python -c "from app.api.settings import router; routes = [r.path for r in router.routes]; print(routes)"
```

Expected output includes: `'/settings/profile'`

---

## Task 5: Update `UserResponse` schema

**Files:**
- Modify: `backend/app/schemas/auth.py`

- [ ] **Step 1: Add fields to `UserResponse`**

```python
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    created_at: datetime
    birth_date: date | None = None
    plan_to_age: int | None = None

    model_config = {"from_attributes": True}
```

---

## Task 6: Inject age context into LLM prompts (overview service)

**Files:**
- Modify: `backend/app/services/overview.py`

- [ ] **Step 1: Find the system prompt construction in overview.py**

```bash
grep -n "system\|prompt\|role\|message\|complete" backend/app/services/overview.py | head -30
```

Note the line numbers where the LLM messages list is built.

- [ ] **Step 2: Inject age context**

In `overview.py`, find the function that builds LLM messages (likely something like `messages = [{"role": "system", ...}]`). Add age context injection before the LLM call:

```python
from app.services.user_context import get_user_age_context

# Inside the function, before building messages:
age_ctx = get_user_age_context(current_user)  # current_user passed as param
age_prefix = f"{age_ctx['prompt']}\n\n" if age_ctx else ""

# Then prepend to the system message content:
# Before: {"role": "system", "content": base_prompt}
# After:  {"role": "system", "content": age_prefix + base_prompt}
```

- [ ] **Step 3: Verify the service still imports cleanly**

```bash
docker compose exec backend python -c "from app.services.overview import *; print('OK')"
```

Expected: `OK`

---

## Task 7: Frontend — `saveProfile` service function

**Files:**
- Modify: `frontend/lib/services/auth.ts`

- [ ] **Step 1: Add profile service functions**

Append to `frontend/lib/services/auth.ts`:

```typescript
export interface ProfileSettings {
  birth_date: string | null;   // ISO date "YYYY-MM-DD"
  plan_to_age: number | null;
  current_age: number | null;
  years_remaining: number | null;
  target_year: number | null;
}

export async function getProfile(): Promise<ProfileSettings | null> {
  const res = await api.get("/api/v1/settings/profile");
  return res.ok ? res.json() : null;
}

export async function saveProfile(data: {
  birth_date?: string | null;
  plan_to_age?: number | null;
}): Promise<ProfileSettings | null> {
  const res = await api.patch("/api/v1/settings/profile", data);
  return res.ok ? res.json() : null;
}
```

---

## Task 8: Frontend — setup wizard profile step

**Files:**
- Modify: `frontend/app/setup/page.tsx`

The wizard currently has 3 steps: `"account" | "hardware" | "llm"`. Add `"profile"` between `"account"` and `"hardware"`. Progress: 25 → 50 → 75 → 100.

- [ ] **Step 1: Replace `frontend/app/setup/page.tsx` with updated 4-step wizard**

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { setupAccount, saveProfile, type HardwareRecommendation } from "@/lib/services/auth";

type Step = "account" | "profile" | "hardware" | "llm";

export default function SetupPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("account");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [hardware, setHardware] = useState<HardwareRecommendation | null>(null);
  const [birthDate, setBirthDate] = useState("");
  const [planToAge, setPlanToAge] = useState("85");
  const [loading, setLoading] = useState(false);

  async function handleCreateAccount(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await setupAccount(username, password);
      if (!result.ok) {
        toast.error(result.error);
        if (result.conflict) router.push("/login");
        return;
      }
      setHardware(result.hardware);
      setStep("profile");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveProfile() {
    setLoading(true);
    try {
      await saveProfile({
        birth_date: birthDate || null,
        plan_to_age: planToAge ? parseInt(planToAge) : null,
      });
    } catch {
      // non-fatal — user can update in settings
    } finally {
      setLoading(false);
    }
    setStep("hardware");
  }

  const stepProgress: Record<Step, number> = {
    account: 25,
    profile: 50,
    hardware: 75,
    llm: 100,
  };

  if (step === "account") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Welcome to Zentri</CardTitle>
            <p className="text-sm text-muted-foreground">Step 1 of 4 — Create your account</p>
            <Progress value={25} className="mt-2" />
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateAccount} className="space-y-4">
              <div className="space-y-1">
                <Label>Username</Label>
                <Input value={username} onChange={(e) => setUsername(e.target.value)} required />
              </div>
              <div className="space-y-1">
                <Label>Password</Label>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={8}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Creating..." : "Create Account"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (step === "profile") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Your Profile</CardTitle>
            <p className="text-sm text-muted-foreground">Step 2 of 4 — Optional</p>
            <Progress value={50} className="mt-2" />
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-muted-foreground">
              Used for age-aware analysis and net worth projections. You can add or change this in Settings later.
            </p>
            <div className="space-y-1">
              <Label>Date of Birth</Label>
              <Input
                type="date"
                value={birthDate}
                onChange={(e) => setBirthDate(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label>Plan to Age</Label>
              <Input
                type="number"
                min={1}
                max={120}
                value={planToAge}
                onChange={(e) => setPlanToAge(e.target.value)}
                placeholder="85"
              />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setStep("hardware")}>
                Skip for now
              </Button>
              <Button className="flex-1" disabled={loading} onClick={handleSaveProfile}>
                {loading ? "Saving..." : "Continue"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (step === "hardware") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Hardware Detected</CardTitle>
            <p className="text-sm text-muted-foreground">Step 3 of 4</p>
            <Progress value={75} className="mt-2" />
          </CardHeader>
          <CardContent className="space-y-4">
            {hardware ? (
              <>
                <div className="rounded-lg border p-3 text-sm space-y-1">
                  <p><strong>Recommended model:</strong> {hardware.recommended_model}</p>
                  <p className="text-muted-foreground">{hardware.note}</p>
                  {hardware.can_run_local_llm && (
                    <code className="block bg-muted p-2 rounded text-xs mt-2">
                      {hardware.setup_command}
                    </code>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  You can always change this in Settings later.
                </p>
              </>
            ) : (
              <p className="text-muted-foreground text-sm">
                Hardware detection unavailable. You can configure LLM in Settings.
              </p>
            )}
            <Button onClick={() => setStep("llm")} className="w-full">
              Continue
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Setup Complete</CardTitle>
          <p className="text-sm text-muted-foreground">Step 4 of 4</p>
          <Progress value={100} className="mt-2" />
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm">
            You can configure LLM providers and API keys in{" "}
            <strong>Settings → LLM Configuration</strong> after you log in.
          </p>
          <Button onClick={() => router.push("/")} className="w-full">
            Go to Dashboard
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
```

---

## Task 9: Frontend — Settings page Profile card

**Files:**
- Modify: `frontend/app/(auth)/settings/page.tsx`

- [ ] **Step 1: Add Profile card to the General tab**

Add the following imports at the top of `frontend/app/(auth)/settings/page.tsx`:

```typescript
import { getProfile, saveProfile, type ProfileSettings } from "@/lib/services/auth";
```

- [ ] **Step 2: Add state variables** (inside `SettingsPage` component, after existing state):

```typescript
const [profile, setProfile] = useState<ProfileSettings | null>(null);
const [birthDate, setBirthDate] = useState("");
const [planToAge, setPlanToAge] = useState("85");
```

- [ ] **Step 3: Add useEffect to load profile** (after existing `useEffect` blocks):

```typescript
useEffect(() => {
  getProfile()
    .then((p) => {
      if (!p) return;
      setProfile(p);
      setBirthDate(p.birth_date ?? "");
      setPlanToAge(p.plan_to_age?.toString() ?? "85");
    })
    .catch(() => null);
}, []);
```

- [ ] **Step 4: Add `saveProfileSettings` function** (after `saveCurrencyPrefs`):

```typescript
async function saveProfileSettings() {
  const result = await saveProfile({
    birth_date: birthDate || null,
    plan_to_age: planToAge ? parseInt(planToAge) : null,
  });
  if (result) setProfile(result);
}
```

- [ ] **Step 5: Add Profile card** inside `<TabsContent value="general">`, after the Display `<Card>` block and before `</TabsContent>`:

```tsx
<Card>
  <CardHeader>
    <CardTitle>Profile</CardTitle>
  </CardHeader>
  <CardContent className="space-y-4">
    <div className="flex gap-4 items-end">
      <div className="flex-1">
        <label className="text-sm font-medium mb-1 block">Date of Birth</label>
        <Input
          type="date"
          value={birthDate}
          onChange={(e) => setBirthDate(e.target.value)}
        />
      </div>
      <div className="flex-1">
        <label className="text-sm font-medium mb-1 block">Plan to Age</label>
        <Input
          type="number"
          min={1}
          max={120}
          value={planToAge}
          onChange={(e) => setPlanToAge(e.target.value)}
          placeholder="85"
        />
      </div>
      <Button
        onClick={async () => {
          try {
            await saveProfileSettings();
            toast.success("Profile saved");
          } catch {
            toast.error("Failed to save profile");
          }
        }}
        className="hover:bg-primary/90 active:scale-95 transition-all cursor-pointer"
      >
        Save
      </Button>
    </div>
    {profile?.current_age != null && (
      <div className="text-xs text-muted-foreground space-y-0.5">
        <p>Current age: {profile.current_age}</p>
        <p>
          Planning horizon: Until {profile.target_year} ({profile.years_remaining} years remaining)
        </p>
      </div>
    )}
  </CardContent>
</Card>
```

---

## Self-Review

**Spec coverage:**
- ✅ DB columns (`birth_date`, `plan_to_age`) — Task 1 + 2
- ✅ Migration — Task 1
- ✅ `get_user_age_context()` helper — Task 3
- ✅ Settings API endpoints — Task 4
- ✅ UserResponse schema — Task 5
- ✅ LLM prompt injection — Task 6
- ✅ Frontend service functions — Task 7
- ✅ Setup wizard 4-step with optional profile step — Task 8
- ✅ Settings Profile card with computed display — Task 9

**Notes:**
- Task 6 (LLM injection) requires reading `overview.py` first (Step 1 is a grep) because the exact function signature is unknown — the step is intentionally open-ended there.
- `plan_to_age` uses `server_default="85"` in migration so existing users get 85 automatically without a data migration.
