# User Age & Planning Horizon

**Date:** 2026-05-05
**Status:** Approved

## Summary

Add `birth_date` and `plan_to_age` to the user profile to enable age-aware financial analysis — net worth projections, retirement planning, and LLM insights like "at your age, you're in the top X% of asset holders."

Both fields are optional. The "death year" / planning end date is never stored — always derived as `birth_date.year + plan_to_age`.

---

## 1. Data Model

New nullable columns on the `users` table:

| Field | Type | Nullable | Default |
|---|---|---|---|
| `birth_date` | `Date` | yes | null |
| `plan_to_age` | `Integer` | yes | 85 |

`plan_to_age` defaults to 85 at the DB level. If `birth_date` is null, LLM context is omitted and projections are not shown.

**Migration:** new Alembic migration file (e.g. `011_user_age_planning.py`).

**Schema changes:**
- `UserResponse` — add `birth_date: date | None`, `plan_to_age: int | None`
- Settings PATCH body — add `birth_date: date | None`, `plan_to_age: int | None`

---

## 2. Setup Wizard (4 steps)

Wizard grows from 3 steps to 4. New step 2 is inserted between "Create Account" and "Hardware Detected":

| Step | Name | Required |
|---|---|---|
| 1 | Create Account | yes |
| 2 | Your Profile (new) | no |
| 3 | Hardware Detected | no |
| 4 | Setup Complete | — |

Progress bar: 25% → 50% → 75% → 100%.

**Step 2 — Your Profile:**
- Date of birth — date input, optional
- Plan to age — number input, pre-filled with 85, optional
- "Continue" button (saves via API if filled)
- "Skip for now" button — equally prominent, skips without saving (`birth_date` stays null; `plan_to_age` gets 85 from the DB default)

---

## 3. Settings Page

Add a **Profile** section (alongside the existing currency section):

**Editable fields:**
- Date of birth — date input, clearable
- Plan to age — number input (min: current age + 1, max: 120)
- Save button scoped to this section

**Read-only computed display (shown only when birthdate is set):**
- Current age
- Planning horizon — e.g. "Until 2065 (40 years remaining)"

---

## 4. LLM Context Injection

**Helper function:** `get_user_age_context(user) -> dict | None`

Returns when `birth_date` is set:
```python
{
    "current_age": int,
    "plan_to_age": int,
    "years_remaining": int,
    "target_year": int,
}
```
Returns `None` when `birth_date` is null.

**Prompt injection** (system prompt prefix when context is available):
```
User context: age {current_age}, planning horizon until age {plan_to_age} ({years_remaining} years remaining).
```

All services that build LLM prompts call this helper and prepend the block when non-null. If null, prompt is unchanged — no regression for users without birthdate.

**Example insights unlocked:**
- "At age 32, you're in the top X% of net worth for your age group"
- "You have 28 years to grow your portfolio to your target"
- "Your current savings rate puts you on track to retire at 58"

---

## Out of Scope

- `retirement_age` field — belongs in a dedicated financial goals feature
- Age-group percentile data — depends on external data source, separate feature
- Mandatory birthdate — both fields remain optional throughout
