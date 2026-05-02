# Import UX Redesign — File-First Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the import wizard so users drop a file first — platform is detected by column signature or named inline — and platform_id is saved on every imported transaction.

**Architecture:** Backend gains a signature-based template lookup so `/import/analyze` works without a platform_id. The frontend drops the platform dropdown from step 1 and inserts a "Name Source" step only when no signature match is found. Platform management (rename/delete) moves to Settings; Portfolio gets an Import shortcut button.

**Tech Stack:** FastAPI + SQLAlchemy (async) + Pydantic v2, Next.js 15 App Router, React Query, TypeScript, Tailwind + shadcn/ui, pytest-asyncio

---

## Pre-flight: Add `platform_id` to transactions migration

Migration 005 creates `provider_configs`, `cash_balances`, and `import_templates` but does **not** add `platform_id` to `transactions`. The Python model already has the column; the DB migration is missing.

- [ ] **Add to `backend/alembic/versions/005_smart_import_llm_cash.py`** inside `upgrade()`, after the existing `op.execute` calls:

```python
op.add_column(
    "transactions",
    sa.Column("platform_id", UUID(as_uuid=True), sa.ForeignKey("platforms.id"), nullable=True),
)
```

And in `downgrade()`:
```python
op.drop_column("transactions", "platform_id")
```

- [ ] Run migration on the dev database:

```bash
cd backend && alembic upgrade head
```

---

## File Map

| File | Change |
|------|--------|
| `backend/app/services/import_pipeline.py` | Add `get_template_by_signature` |
| `backend/app/schemas/import_template.py` | Add `matched_platform_id` to `AnalyzeResponse` |
| `backend/app/api/import_pipeline.py` | Optional `platform_id` in `analyze_file`; pass `platform_id` in `confirm_import` |
| `backend/app/api/platforms.py` | Add `PATCH /platforms/{id}` endpoint |
| `backend/app/services/platform.py` | Add `rename_platform` |
| `backend/tests/test_import_api.py` | Replace with new tests for file-first flow |
| `frontend/lib/services/import-pipeline.ts` | Update `AnalyzeResponse` type; make `platform_id` optional in `analyzeFile` |
| `frontend/lib/services/platforms.ts` | Add `renamePlatform` |
| `frontend/app/(auth)/import/page.tsx` | Full rewrite — file-first wizard |
| `frontend/app/(auth)/portfolio/page.tsx` | Add Import button to page header |
| `frontend/app/(auth)/settings/page.tsx` | Add Platforms section (list + rename + delete) |

---

## Task 1: Add `get_template_by_signature` service function

**Files:**
- Modify: `backend/app/services/import_pipeline.py`
- Test: `backend/tests/test_import_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_import_pipeline.py
import pytest
import uuid
from app.services.import_pipeline import get_template_by_signature, save_template

@pytest.mark.asyncio
async def test_get_template_by_signature_not_found(db):
    result = await get_template_by_signature(db, uuid.uuid4(), "nonexistent_sig")
    assert result is None

@pytest.mark.asyncio
async def test_get_template_by_signature_found(db, auth_client):
    # Create a platform first
    p = await auth_client.post("/api/v1/platforms", json={"name": "Test", "asset_types_supported": []})
    pid = uuid.UUID(p.json()["id"])
    # We need user_id — get it from auth_client's token
    me = await auth_client.get("/api/v1/auth/me")
    user_id = uuid.UUID(me.json()["id"])

    await save_template(
        db, user_id, pid,
        {"field_map": {}, "asset_type_rules": [], "asset_type_fallback": "us_stock", "currency_default": "THB"},
        "csv", None, "abc123"
    )
    result = await get_template_by_signature(db, user_id, "abc123")
    assert result is not None
    assert result.platform_id == pid
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_import_pipeline.py::test_get_template_by_signature_not_found tests/test_import_pipeline.py::test_get_template_by_signature_found -v
```

Expected: `AttributeError` or `ImportError` — `get_template_by_signature` does not exist yet.

- [ ] **Step 3: Implement `get_template_by_signature` in `backend/app/services/import_pipeline.py`**

Add this function after the existing `get_template` function:

```python
async def get_template_by_signature(
    db: AsyncSession, user_id: uuid.UUID, signature: str
) -> ImportTemplate | None:
    result = await db.execute(
        select(ImportTemplate).where(
            ImportTemplate.user_id == user_id,
            ImportTemplate.column_signature == signature,
        )
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_import_pipeline.py::test_get_template_by_signature_not_found tests/test_import_pipeline.py::test_get_template_by_signature_found -v
```

Expected: both PASS.

---

## Task 2: Update `AnalyzeResponse` schema

**Files:**
- Modify: `backend/app/schemas/import_template.py`

- [ ] **Step 1: Update `AnalyzeResponse` to include `matched_platform_id`**

Replace the `AnalyzeResponse` class in `backend/app/schemas/import_template.py`:

```python
class AnalyzeResponse(BaseModel):
    signature: str
    structure: dict
    template_status: str  # "match" | "mismatch" | "new"
    template: ImportTemplateOut | None
    preview_rows: list[dict] | None
    matched_platform_id: uuid.UUID | None = None  # set when signature lookup finds a match
```

No test needed — this is validated by Task 3's endpoint tests.

---

## Task 3: Update `/import/analyze` to accept optional `platform_id`

**Files:**
- Modify: `backend/app/api/import_pipeline.py`
- Test: `backend/tests/test_import_api.py`

- [ ] **Step 1: Write failing tests**

Replace `backend/tests/test_import_api.py` with:

```python
import pytest
import uuid

CSV_CONTENT = b"Template,Fund_Code,Trade_Date,Total_Amount,Number_of_Units\nManual,K-VIETNAM,2026-01-01,500,10"


@pytest.mark.asyncio
async def test_analyze_without_platform_id_returns_new(auth_client):
    resp = await auth_client.post(
        "/api/v1/import/analyze",
        files={"file": ("transactions.csv", CSV_CONTENT, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["template_status"] == "new"
    assert data["matched_platform_id"] is None


@pytest.mark.asyncio
async def test_analyze_without_platform_id_returns_match_after_template_exists(auth_client):
    # Create platform and save a template via generate-template
    p = await auth_client.post("/api/v1/platforms", json={"name": "Finnomena", "asset_types_supported": ["th_fund"]})
    pid = p.json()["id"]

    # First analyze with platform_id to get signature
    resp1 = await auth_client.post(
        "/api/v1/import/analyze",
        data={"platform_id": pid},
        files={"file": ("transactions.csv", CSV_CONTENT, "text/csv")},
    )
    assert resp1.status_code == 200
    assert resp1.json()["template_status"] == "new"

    # Generate template (saves it)
    await auth_client.post(
        "/api/v1/import/generate-template",
        data={"platform_id": pid},
        files={"file": ("transactions.csv", CSV_CONTENT, "text/csv")},
    )

    # Now analyze WITHOUT platform_id — should find via signature
    resp2 = await auth_client.post(
        "/api/v1/import/analyze",
        files={"file": ("transactions.csv", CSV_CONTENT, "text/csv")},
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["template_status"] == "match"
    assert data["matched_platform_id"] == pid


@pytest.mark.asyncio
async def test_analyze_with_platform_id_still_works(auth_client):
    p = await auth_client.post("/api/v1/platforms", json={"name": "Test", "asset_types_supported": []})
    pid = p.json()["id"]
    resp = await auth_client.post(
        "/api/v1/import/analyze",
        data={"platform_id": pid},
        files={"file": ("transactions.csv", CSV_CONTENT, "text/csv")},
    )
    assert resp.status_code == 200
    assert resp.json()["template_status"] == "new"


@pytest.mark.asyncio
async def test_confirm_saves_platform_id_on_transactions(auth_client, db):
    from sqlalchemy import select
    from app.models.transaction import Transaction

    rows = [{"symbol": "AAPL", "type": "buy", "units": "10", "price": "150", "date": "2026-01-01", "asset_type": "us_stock", "currency": "USD"}]
    p = await auth_client.post("/api/v1/platforms", json={"name": "IBKR", "asset_types_supported": ["us_stock"]})
    pid = p.json()["id"]

    resp = await auth_client.post("/api/v1/import/confirm", json={"platform_id": pid, "rows": rows})
    assert resp.status_code == 200
    assert resp.json()["imported"] == 1

    result = await db.execute(select(Transaction))
    txs = result.scalars().all()
    assert len(txs) == 1
    assert str(txs[0].platform_id) == pid
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_import_api.py -v
```

Expected: failures — `analyze` requires `platform_id`, `matched_platform_id` field missing, confirm doesn't save platform_id.

- [ ] **Step 3: Update `analyze_file` endpoint in `backend/app/api/import_pipeline.py`**

Replace the `analyze_file` function:

```python
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_file(
    file: UploadFile = File(...),
    platform_id: uuid.UUID | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    file_format = pipeline_svc.detect_file_format(file.filename or "", content)
    json_path = None
    structure = pipeline_svc.extract_structure(file_format, content, json_path)
    signature = pipeline_svc.compute_signature(structure["headers"])

    matched_platform_id: uuid.UUID | None = None

    if platform_id is not None:
        existing_template = await pipeline_svc.get_template(db, current_user.id, platform_id)
        if not existing_template:
            status = "new"
            preview = None
        elif existing_template.column_signature != signature:
            status = "mismatch"
            preview = None
        else:
            status = "match"
            matched_platform_id = platform_id
            tmpl_dict = {
                "field_map": existing_template.field_map,
                "asset_type_rules": existing_template.asset_type_rules,
                "asset_type_fallback": existing_template.asset_type_fallback,
                "currency_default": existing_template.currency_default,
            }
            preview = pipeline_svc.apply_template(structure["all_rows"], tmpl_dict)
    else:
        existing_template = await pipeline_svc.get_template_by_signature(db, current_user.id, signature)
        if existing_template:
            status = "match"
            matched_platform_id = existing_template.platform_id
            tmpl_dict = {
                "field_map": existing_template.field_map,
                "asset_type_rules": existing_template.asset_type_rules,
                "asset_type_fallback": existing_template.asset_type_fallback,
                "currency_default": existing_template.currency_default,
            }
            preview = pipeline_svc.apply_template(structure["all_rows"], tmpl_dict)
        else:
            status = "new"
            preview = None

    logger.info(
        "Import analyze: platform=%s format=%s status=%s user=%s",
        platform_id, file_format, status, current_user.id,
    )
    return AnalyzeResponse(
        signature=signature,
        structure={"headers": structure["headers"], "sample_rows": structure["sample_rows"], "total_rows": structure["total_rows"]},
        template_status=status,
        template=ImportTemplateOut.model_validate(existing_template) if existing_template else None,
        preview_rows=preview,
        matched_platform_id=matched_platform_id,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_import_api.py::test_analyze_without_platform_id_returns_new tests/test_import_api.py::test_analyze_with_platform_id_still_works -v
```

Expected: both PASS. (The signature-match test needs Task 4 to also pass.)

---

## Task 4: Update `/import/confirm` to pass `platform_id` and fix source enum

**Files:**
- Modify: `backend/app/api/import_pipeline.py`

`add_transaction` already accepts `platform_id` — only the call site needs updating. Also: `source="import_pipeline"` is not in `TRANSACTION_SOURCES = ("manual", "csv_import")` — it must be `"csv_import"` to avoid a DB enum error.

- [ ] **Step 1: Update the `add_transaction` call in `confirm_import`**

Find this line in `backend/app/api/import_pipeline.py`:
```python
await portfolio_service.add_transaction(
    db, current_user.id, asset.id, tx_type, quantity, price, fee, executed_at, source="import_pipeline"
)
```

Replace with:
```python
await portfolio_service.add_transaction(
    db, current_user.id, asset.id, tx_type, quantity, price, fee, executed_at,
    source="csv_import",
    platform_id=body.platform_id,
)
```

- [ ] **Step 2: Run the confirm test**

```bash
cd backend && python -m pytest tests/test_import_api.py::test_confirm_saves_platform_id_on_transactions -v
```

Expected: PASS.

- [ ] **Step 3: Run full test suite to check for regressions**

```bash
cd backend && python -m pytest tests/test_import_api.py -v
```

Expected: all tests PASS.

---

## Task 5: Add platform rename endpoint

**Files:**
- Modify: `backend/app/services/platform.py`
- Modify: `backend/app/api/platforms.py`

- [ ] **Step 1: Add `rename_platform` to `backend/app/services/platform.py`**

Open the file and add:

```python
async def rename_platform(
    db: AsyncSession, user_id: uuid.UUID, platform_id: uuid.UUID, new_name: str
) -> Platform | None:
    result = await db.execute(
        select(Platform).where(Platform.id == platform_id, Platform.user_id == user_id)
    )
    platform = result.scalar_one_or_none()
    if platform is None:
        return None
    platform.name = new_name
    await db.commit()
    await db.refresh(platform)
    return platform
```

Make sure `Platform` and `AsyncSession` are already imported; add them if not.

- [ ] **Step 2: Add `PATCH /platforms/{platform_id}` to `backend/app/api/platforms.py`**

Add this endpoint to the existing router:

```python
from pydantic import BaseModel

class PlatformRenameRequest(BaseModel):
    name: str

@router.patch("/{platform_id}", response_model=PlatformOut)
async def rename_platform_endpoint(
    platform_id: uuid.UUID,
    body: PlatformRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import platform as platform_svc
    updated = await platform_svc.rename_platform(db, current_user.id, platform_id, body.name)
    if updated is None:
        raise HTTPException(status_code=404, detail="Platform not found")
    return updated
```

Check that `PlatformOut` is the existing response schema — if it's named differently, use the correct name.

- [ ] **Step 3: Quick smoke test**

```bash
cd backend && python -m pytest tests/ -v -k "platform" 2>&1 | head -30
```

Expected: existing platform tests still pass.

---

## Task 6: Update frontend `import-pipeline.ts` types

**Files:**
- Modify: `frontend/lib/services/import-pipeline.ts`

- [ ] **Step 1: Update `AnalyzeResponse` type and `analyzeFile` signature**

Replace the entire contents of `frontend/lib/services/import-pipeline.ts`:

```typescript
import { api } from "@/lib/api";

export interface AnalyzeResponse {
  signature: string;
  structure: {
    headers: string[];
    sample_rows: Record<string, unknown>[];
    total_rows: number;
  };
  template_status: "match" | "mismatch" | "new";
  template: ImportTemplate | null;
  preview_rows: Record<string, unknown>[] | null;
  matched_platform_id: string | null;
}

export interface ImportTemplate {
  id: string;
  platform_id: string;
  file_format: string;
  json_path: string | null;
  column_signature: string;
  field_map: Record<string, string>;
  asset_type_rules: unknown[];
  asset_type_fallback: string;
  currency_default: string;
  updated_at: string;
}

export async function analyzeFile(file: File): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch("/api/v1/import/analyze", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${
        typeof window !== "undefined" ? localStorage.getItem("access_token") : ""
      }`,
    },
    body: form,
  });
  if (!r.ok) throw new Error("Failed to analyze file");
  return r.json();
}

export async function generateTemplate(
  platform_id: string,
  file: File,
): Promise<{ template: ImportTemplate; preview_rows: Record<string, unknown>[] }> {
  const form = new FormData();
  form.append("platform_id", platform_id);
  form.append("file", file);
  const r = await fetch("/api/v1/import/generate-template", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${
        typeof window !== "undefined" ? localStorage.getItem("access_token") : ""
      }`,
    },
    body: form,
  });
  if (!r.ok) throw new Error("Failed to generate template");
  return r.json();
}

export async function confirmImportPipeline(
  platform_id: string,
  rows: Record<string, unknown>[],
): Promise<{ imported: number; errors: unknown[] }> {
  const r = await fetch("/api/v1/import/confirm", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${
        typeof window !== "undefined" ? localStorage.getItem("access_token") : ""
      }`,
    },
    body: JSON.stringify({ platform_id, rows }),
  });
  if (!r.ok) throw new Error("Failed to confirm import");
  return r.json();
}
```

---

## Task 7: Add `renamePlatform` to frontend platforms service

**Files:**
- Modify: `frontend/lib/services/platforms.ts`

- [ ] **Step 1: Add `renamePlatform` function**

Open `frontend/lib/services/platforms.ts` and add after `deletePlatform`:

```typescript
export async function renamePlatform(id: string, name: string): Promise<Platform> {
  const res = await api.patch(`/api/v1/platforms/${id}`, { name });
  if (!res.ok) throw new Error("Failed to rename platform");
  return res.json();
}
```

---

## Task 8: Rewrite import page — file-first wizard

**Files:**
- Modify: `frontend/app/(auth)/import/page.tsx`

This is a full rewrite. Replace the entire file:

- [ ] **Step 1: Replace `frontend/app/(auth)/import/page.tsx`**

```tsx
"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { fetchPlatforms, createPlatform } from "@/lib/services/platforms";
import {
  analyzeFile,
  generateTemplate,
  confirmImportPipeline,
  type AnalyzeResponse,
} from "@/lib/services/import-pipeline";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";

type Step = "upload" | "name-source" | "review" | "done";

export default function ImportPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResponse | null>(null);
  const [platformId, setPlatformId] = useState<string>("");
  const [newPlatformName, setNewPlatformName] = useState("");
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  const [importedCount, setImportedCount] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: platforms = [], refetch: refetchPlatforms } = useQuery({
    queryKey: ["platforms"],
    queryFn: fetchPlatforms,
  });

  async function handleAnalyze() {
    if (!file) {
      toast.error("Please select a file.");
      return;
    }
    setAnalyzing(true);
    try {
      const result = await analyzeFile(file);
      setAnalyzeResult(result);

      if (result.template_status === "match" && result.preview_rows && result.matched_platform_id) {
        setPlatformId(result.matched_platform_id);
        setPreviewRows(result.preview_rows);
        setStep("review");
      } else {
        setStep("name-source");
      }
    } catch {
      toast.error("Failed to analyze file. Please try again.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleConfirmSource() {
    if (!file || !analyzeResult) return;

    let resolvedPlatformId = platformId;

    if (!resolvedPlatformId && newPlatformName.trim()) {
      try {
        const created = await createPlatform({
          name: newPlatformName.trim(),
          asset_types_supported: [],
        });
        resolvedPlatformId = created.id;
        setPlatformId(created.id);
        await refetchPlatforms();
      } catch {
        toast.error("Failed to create platform.");
        return;
      }
    }

    if (!resolvedPlatformId) {
      toast.error("Please select or name a source platform.");
      return;
    }

    setGenerating(true);
    try {
      const result = await generateTemplate(resolvedPlatformId, file);
      setPreviewRows(result.preview_rows);
      setStep("review");
      toast.success("Template generated successfully.");
    } catch {
      toast.error("Failed to generate template.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleConfirmImport() {
    if (!platformId || previewRows.length === 0) return;
    setConfirming(true);
    try {
      const result = await confirmImportPipeline(platformId, previewRows);
      setImportedCount(result.imported);
      setStep("done");
      if (result.errors && result.errors.length > 0) {
        toast.warning(`${result.errors.length} row(s) had errors during import.`);
      }
    } catch {
      toast.error("Failed to confirm import.");
    } finally {
      setConfirming(false);
    }
  }

  function handleReset() {
    setStep("upload");
    setFile(null);
    setAnalyzeResult(null);
    setPlatformId("");
    setNewPlatformName("");
    setPreviewRows([]);
    setImportedCount(0);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  const previewHeaders = previewRows.length > 0 ? Object.keys(previewRows[0]) : [];
  const displayRows = previewRows.slice(0, 20);
  const matchedPlatformName = platforms.find((p) => p.id === platformId)?.name;

  const STEPS: Step[] = ["upload", "name-source", "review", "done"];
  const STEP_LABELS: Record<Step, string> = {
    "upload": "Upload",
    "name-source": "Source",
    "review": "Review",
    "done": "Done",
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Import</h1>

      {/* Step indicator */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {STEPS.map((s, i) => (
          <span key={s} className="flex items-center gap-2">
            <span className={step === s ? "font-semibold text-foreground" : ""}>
              {i + 1}. {STEP_LABELS[s]}
            </span>
            {i < STEPS.length - 1 && <span>›</span>}
          </span>
        ))}
      </div>

      {/* Step: Upload */}
      {step === "upload" && (
        <Card>
          <CardHeader>
            <CardTitle>Upload File</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">File (CSV or JSON)</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.json"
                className="w-full border rounded-md px-3 py-2 text-sm bg-background file:mr-2 file:border-0 file:bg-transparent file:text-sm file:font-medium"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
            <button
              onClick={handleAnalyze}
              disabled={analyzing || !file}
              className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
            >
              {analyzing ? "Analyzing…" : "Analyze"}
            </button>
          </CardContent>
        </Card>
      )}

      {/* Step: Name Source */}
      {step === "name-source" && (
        <Card>
          <CardHeader>
            <CardTitle>Name the Source</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              No saved template matched this file. Select an existing source or type a new name.
            </p>

            {platforms.length > 0 && (
              <div className="space-y-1">
                <label className="text-sm font-medium">Existing platforms</label>
                <div className="flex flex-wrap gap-2">
                  {platforms.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => {
                        setPlatformId(p.id);
                        setNewPlatformName("");
                      }}
                      className={`px-3 py-1 rounded-full border text-sm ${
                        platformId === p.id
                          ? "bg-primary text-primary-foreground border-primary"
                          : "text-muted-foreground hover:bg-accent"
                      }`}
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-1">
              <label className="text-sm font-medium">
                {platforms.length > 0 ? "Or create a new one" : "Platform / broker name"}
              </label>
              <input
                type="text"
                placeholder="e.g. Finnomena, IBKR, Bitkub"
                value={newPlatformName}
                onChange={(e) => {
                  setNewPlatformName(e.target.value);
                  setPlatformId("");
                }}
                className="w-full border rounded-md px-3 py-2 text-sm bg-background"
              />
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleConfirmSource}
                disabled={generating || (!platformId && !newPlatformName.trim())}
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
              >
                {generating ? "Generating template…" : "Continue"}
              </button>
              <button
                onClick={handleReset}
                className="px-4 py-2 rounded-md border text-sm font-medium"
              >
                Back
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step: Review */}
      {step === "review" && (
        <Card>
          <CardHeader>
            <CardTitle>Review Preview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {matchedPlatformName && (
              <p className="text-sm">
                Source: <span className="font-medium">{matchedPlatformName}</span>
              </p>
            )}
            <p className="text-sm text-muted-foreground">
              Showing first {displayRows.length} of {previewRows.length} rows. Confirm to import all.
            </p>

            {previewHeaders.length > 0 ? (
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-xs">
                  <thead className="bg-muted">
                    <tr>
                      {previewHeaders.map((h) => (
                        <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {displayRows.map((row, i) => (
                      <tr key={i} className="border-t">
                        {previewHeaders.map((h) => (
                          <td key={h} className="px-3 py-2 whitespace-nowrap text-muted-foreground">
                            {String(row[h] ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No preview data available.</p>
            )}

            <div className="flex gap-2">
              <button
                onClick={handleConfirmImport}
                disabled={confirming}
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
              >
                {confirming ? "Importing…" : "Confirm Import"}
              </button>
              <button onClick={handleReset} className="px-4 py-2 rounded-md border text-sm font-medium">
                Cancel
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step: Done */}
      {step === "done" && (
        <Card>
          <CardHeader>
            <CardTitle>Import Complete</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Successfully imported{" "}
              <span className="font-semibold text-foreground">{importedCount}</span>{" "}
              row{importedCount !== 1 ? "s" : ""} into your portfolio.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => router.push("/portfolio")}
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium"
              >
                Go to Portfolio
              </button>
              <button onClick={handleReset} className="px-4 py-2 rounded-md border text-sm font-medium">
                Import Another File
              </button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

---

## Task 9: Add Import button to Portfolio page

**Files:**
- Modify: `frontend/app/(auth)/portfolio/page.tsx`

- [ ] **Step 1: Open the file and locate the page header**

Find the `<h1>` or page title element. It likely looks like:
```tsx
<h1 className="text-2xl font-bold">Portfolio</h1>
```

- [ ] **Step 2: Replace the header with a flex row that includes the Import button**

```tsx
import Link from "next/link";

// Replace the existing header line with:
<div className="flex items-center justify-between">
  <h1 className="text-2xl font-bold">Portfolio</h1>
  <Link
    href="/import"
    className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium"
  >
    Import
  </Link>
</div>
```

If `Link` is already imported, skip the import statement.

---

## Task 10: Add Platforms section to Settings page

**Files:**
- Modify: `frontend/app/(auth)/settings/page.tsx`

- [ ] **Step 1: Read the current settings page** to understand existing structure before editing.

- [ ] **Step 2: Add platforms management section**

Add the following imports at the top of the file (merge with existing imports):

```tsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchPlatforms, renamePlatform, deletePlatform } from "@/lib/services/platforms";
import { toast } from "sonner";
```

Add a `PlatformsSection` component (can be defined in the same file):

```tsx
function PlatformsSection() {
  const queryClient = useQueryClient();
  const { data: platforms = [] } = useQuery({
    queryKey: ["platforms"],
    queryFn: fetchPlatforms,
  });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => renamePlatform(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platforms"] });
      setEditingId(null);
      toast.success("Platform renamed.");
    },
    onError: () => toast.error("Failed to rename platform."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deletePlatform(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platforms"] });
      toast.success("Platform deleted.");
    },
    onError: () => toast.error("Failed to delete platform."),
  });

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold">Platforms</h2>
      {platforms.length === 0 ? (
        <p className="text-sm text-muted-foreground">No platforms yet. They are created automatically during import.</p>
      ) : (
        <ul className="space-y-2">
          {platforms.map((p) => (
            <li key={p.id} className="flex items-center gap-2 rounded-md border px-3 py-2">
              {editingId === p.id ? (
                <>
                  <input
                    className="flex-1 border rounded px-2 py-1 text-sm bg-background"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") renameMutation.mutate({ id: p.id, name: editName });
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    autoFocus
                  />
                  <button
                    onClick={() => renameMutation.mutate({ id: p.id, name: editName })}
                    className="text-sm text-primary font-medium"
                  >
                    Save
                  </button>
                  <button onClick={() => setEditingId(null)} className="text-sm text-muted-foreground">
                    Cancel
                  </button>
                </>
              ) : (
                <>
                  <span className="flex-1 text-sm">{p.name}</span>
                  <button
                    onClick={() => { setEditingId(p.id); setEditName(p.name); }}
                    className="text-sm text-muted-foreground hover:text-foreground"
                  >
                    Rename
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(p.id)}
                    className="text-sm text-destructive hover:underline"
                  >
                    Delete
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

Add `<PlatformsSection />` to the settings page body, after existing sections.

Add `import { useState } from "react";` if not already imported.

---

## Final verification

- [ ] Run full backend test suite:

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] Check TypeScript compilation:

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] Manual smoke test:
  1. Navigate to `/import`
  2. Upload a CSV file — confirm no platform dropdown shown
  3. If new file: "Name Source" step appears with existing platforms as chips + text input
  4. After import: navigate to `/portfolio`, verify Import button is present
  5. Go to `/settings`, verify Platforms section lists created platform with rename/delete
