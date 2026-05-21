# Document Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent duplicate documents (system downloads + manual uploads) using SHA-256 content hashing with a DB unique constraint as the authoritative guard, and fix the Documents page silent failure.

**Architecture:** Add `content_hash VARCHAR(64)` to `documents` with a partial unique index. Both download and upload paths compute the hash before inserting; duplicates are caught at the DB constraint level (race-condition-proof). Manual uploads return HTTP 409 with existing doc info so the frontend can offer a Replace flow. The Documents page gets an explicit error state.

**Tech Stack:** Python `hashlib` (stdlib), SQLAlchemy `IntegrityError`, FastAPI `Query`, Next.js React state + Dialog component (already in project).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/alembic/versions/040_add_content_hash.py` | Create | Add `content_hash` column + partial unique index |
| `backend/app/models/document.py` | Modify | Add `content_hash` mapped column |
| `backend/app/services/document_manager.py` | Modify | Hash dedup in `pre_fetch()` |
| `backend/app/api/documents.py` | Modify | Hash check + 409 + replace logic in upload |
| `backend/tests/test_document_manager.py` | Create | Unit tests for hash dedup in pre_fetch |
| `backend/tests/test_upload_dedup.py` | Create | Tests for upload 409 + replace endpoint |
| `frontend/app/(auth)/documents/page.tsx` | Modify | Duplicate modal + error state |

---

## Task 1: Migration — add `content_hash` column

**Files:**
- Create: `backend/alembic/versions/040_add_content_hash.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/040_add_content_hash.py
"""add content_hash to documents

Revision ID: 040
Revises: 039
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_documents_content_hash_unique",
        "documents",
        ["content_hash"],
        unique=True,
        postgresql_where=sa.text("content_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_content_hash_unique", table_name="documents")
    op.drop_column("documents", "content_hash")
```

- [ ] **Step 2: Run the migration**

```bash
docker compose exec backend alembic upgrade head
```

Expected output ends with: `Running upgrade 039 -> 040`

- [ ] **Step 3: Verify the column exists**

```bash
docker compose exec db psql -U zentri -d zentri -c "\d documents" | grep content_hash
```

Expected: `content_hash | character varying(64) | | |`

---

## Task 2: Add `content_hash` field to `Document` model

**Files:**
- Modify: `backend/app/models/document.py`

- [ ] **Step 1: Add the field**

Open `backend/app/models/document.py`. After the `doc_type` field, add:

```python
content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

The full model should look like this after the change:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(nullable=False)
    file_path: Mapped[str] = mapped_column(nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="pending")
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chroma_collection_id: Mapped[str | None] = mapped_column(nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Verify app starts without errors**

```bash
docker compose restart backend worker
docker compose logs backend --tail=20
```

Expected: no `ImportError` or `AttributeError`.

---

## Task 3: Hash dedup in `DocumentManager.pre_fetch()`

**Files:**
- Modify: `backend/app/services/document_manager.py`
- Create: `backend/tests/test_document_manager.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_document_manager.py`:

```python
import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.document_manager import DocumentManager


@pytest.mark.asyncio
async def test_pre_fetch_skips_duplicate_content_hash():
    """Same content downloaded twice should be skipped on second call."""
    manager = DocumentManager()
    content = b"<html>10-K filing content</html>"
    content_hash = hashlib.sha256(content).hexdigest()

    # URL check returns None (not a URL-level dup)
    # Hash check returns an existing document
    existing_doc = MagicMock()
    existing_doc.id = uuid.uuid4()

    db = AsyncMock()
    url_check_result = MagicMock()
    url_check_result.scalar_one_or_none.return_value = None
    hash_check_result = MagicMock()
    hash_check_result.scalar_one_or_none.return_value = existing_doc
    db.execute.side_effect = [url_check_result, hash_check_result]

    with patch.object(manager, "_download", return_value=content), \
         patch.object(manager, "_save_file"), \
         patch.object(manager, "_enqueue_ingest"):
        result = await manager.pre_fetch(
            ticker="AAPL",
            asset_id=uuid.uuid4(),
            doc_items=[{
                "url": "https://sec.gov/Archives/10-K.htm",
                "doc_type": "10-K",
                "filename": "10-K_001.htm",
            }],
            db=db,
        )

    assert result["skipped"] == 1
    assert result["fetched"] == 0


@pytest.mark.asyncio
async def test_pre_fetch_saves_content_hash_on_new_doc():
    """New document should be saved with content_hash set."""
    manager = DocumentManager()
    content = b"<html>fresh 10-K content</html>"
    expected_hash = hashlib.sha256(content).hexdigest()
    asset_id = uuid.uuid4()

    db = AsyncMock()
    # Both URL check and hash check return None (new doc)
    no_result = MagicMock()
    no_result.scalar_one_or_none.return_value = None
    db.execute.side_effect = [no_result, no_result]

    saved_doc = None

    def capture_add(doc):
        nonlocal saved_doc
        saved_doc = doc

    db.add.side_effect = capture_add

    with patch.object(manager, "_download", return_value=content), \
         patch.object(manager, "_save_file", return_value="/app/uploads/AAPL/10-K/doc.htm"), \
         patch.object(manager, "_enqueue_ingest"):
        result = await manager.pre_fetch(
            ticker="AAPL",
            asset_id=asset_id,
            doc_items=[{
                "url": "https://sec.gov/Archives/10-K.htm",
                "doc_type": "10-K",
                "filename": "10-K_001.htm",
            }],
            db=db,
        )

    assert result["fetched"] == 1
    assert saved_doc is not None
    assert saved_doc.content_hash == expected_hash
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec backend pytest tests/test_document_manager.py -v
```

Expected: `FAILED` — `pre_fetch` doesn't check by hash yet.

- [ ] **Step 3: Update `DocumentManager.pre_fetch()` with hash dedup**

Open `backend/app/services/document_manager.py`. Add `import hashlib` at the top, then update `pre_fetch()`:

```python
from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.document import Document

logger = get_logger(__name__)

EDGAR_HEADERS = {"User-Agent": "Zentri contact@zentri.app"}


def _upload_dir() -> Path:
    return Path(os.getenv("UPLOAD_DIR", "/app/uploads"))


class DocumentManager:
    async def _download(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url, headers=EDGAR_HEADERS)
            resp.raise_for_status()
            return resp.content

    def _save_file(self, content: bytes, ticker: str, doc_type: str, doc_id: uuid.UUID, filename: str) -> str:
        dest_dir = _upload_dir() / ticker.upper() / doc_type.replace("/", "_")
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = Path(filename).name
        dest = dest_dir / f"{doc_id}_{safe_filename}"
        dest.write_bytes(content)
        return str(dest)

    async def _enqueue_ingest(self, doc_id: uuid.UUID) -> None:
        try:
            from arq.connections import ArqRedis, RedisSettings, create_pool
            from app.core.config import settings
            redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
            await redis.enqueue_job("job_ingest_document", str(doc_id))
            await redis.aclose()
        except Exception as e:
            logger.warning("document_manager: failed to enqueue ingest doc_id=%s: %s", doc_id, e)

    async def check_exists(self, source_url: str, db: AsyncSession) -> Document | None:
        result = await db.execute(
            select(Document).where(Document.source_url == source_url)
        )
        return result.scalar_one_or_none()

    async def _check_hash_exists(self, content_hash: str, db: AsyncSession) -> Document | None:
        result = await db.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def pre_fetch(
        self,
        ticker: str,
        asset_id: uuid.UUID | None,
        doc_items: list[dict],
        db: AsyncSession,
    ) -> dict:
        fetched = 0
        skipped = 0
        failed = 0

        for item in doc_items:
            url = item["url"]
            doc_type = item["doc_type"]
            filename = item["filename"]

            existing = await self.check_exists(url, db)
            if existing:
                logger.info("document_manager: skip existing source_url=%s", url)
                skipped += 1
                continue

            try:
                content = await self._download(url)
                content_hash = hashlib.sha256(content).hexdigest()

                hash_existing = await self._check_hash_exists(content_hash, db)
                if hash_existing:
                    logger.info("document_manager: skip duplicate content hash=%s url=%s", content_hash[:8], url)
                    skipped += 1
                    continue

                doc_id = uuid.uuid4()
                file_path = self._save_file(content, ticker, doc_type, doc_id, filename)

                doc = Document(
                    id=doc_id,
                    filename=filename,
                    file_path=file_path,
                    asset_id=asset_id,
                    source_url=url,
                    doc_type=doc_type,
                    content_hash=content_hash,
                    status="pending",
                )
                db.add(doc)
                try:
                    await db.flush()
                except IntegrityError:
                    await db.rollback()
                    logger.info("document_manager: concurrent duplicate content_hash=%s, skipping", content_hash[:8])
                    skipped += 1
                    continue
                await self._enqueue_ingest(doc_id)
                fetched += 1
                logger.info("document_manager: fetched doc_id=%s url=%s", doc_id, url)
            except Exception as e:
                failed += 1
                logger.warning("document_manager: failed url=%s: %s", url, e)

        if fetched > 0:
            await db.commit()

        return {"fetched": fetched, "skipped": skipped, "failed": failed}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
docker compose exec backend pytest tests/test_document_manager.py -v
```

Expected: `2 passed`

---

## Task 4: Hash check + 409 + replace in upload endpoint

**Files:**
- Modify: `backend/app/api/documents.py`
- Create: `backend/tests/test_upload_dedup.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_upload_dedup.py`:

```python
import hashlib
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.document import Document
from app.models.user import User


def make_mock_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    return user


def make_mock_db():
    return AsyncMock(spec=AsyncSession)


@contextmanager
def client_with_db(mock_db):
    def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = make_mock_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_upload_returns_409_when_content_already_exists():
    content = b"<html>identical content</html>"
    content_hash = hashlib.sha256(content).hexdigest()

    existing_doc = MagicMock(spec=Document)
    existing_doc.id = uuid.uuid4()
    existing_doc.filename = "already_uploaded.htm"
    existing_doc.content_hash = content_hash

    mock_db = make_mock_db()
    hash_check_result = MagicMock()
    hash_check_result.scalar_one_or_none.return_value = existing_doc
    mock_db.execute.return_value = hash_check_result

    with client_with_db(mock_db) as c:
        response = c.post(
            "/api/v1/documents/upload",
            files={"file": ("new_upload.htm", content, "text/html")},
            data={"doc_type": "general"},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["existing_id"] == str(existing_doc.id)
    assert body["existing_filename"] == "already_uploaded.htm"


def test_upload_succeeds_with_replace_id():
    content = b"<html>replacement content</html>"
    replace_id = uuid.uuid4()

    old_doc = MagicMock(spec=Document)
    old_doc.id = replace_id
    old_doc.chroma_collection_id = None
    old_doc.file_path = "/tmp/old_file.htm"

    mock_db = make_mock_db()
    hash_check = MagicMock()
    hash_check.scalar_one_or_none.return_value = None
    old_doc_result = MagicMock()
    old_doc_result.scalar_one_or_none.return_value = old_doc
    asset_result = MagicMock()
    asset_result.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [hash_check, old_doc_result, asset_result]

    with client_with_db(mock_db) as c:
        with patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.write_bytes"), \
             patch("pathlib.Path.unlink"):
            response = c.post(
                f"/api/v1/documents/upload?replace_id={replace_id}",
                files={"file": ("new.htm", content, "text/html")},
                data={"doc_type": "general"},
            )

    assert response.status_code == 202
    assert "document_id" in response.json()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec backend pytest tests/test_upload_dedup.py -v
```

Expected: `FAILED` — endpoint doesn't check hash yet.

- [ ] **Step 3: Update the upload endpoint**

Replace the `upload_document` function in `backend/app/api/documents.py`:

```python
import hashlib
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.document import Document
from app.models.user import User

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)


def _upload_dir() -> Path:
    return Path(os.getenv("UPLOAD_DIR", "/app/uploads"))


@router.post("/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(default="general"),
    asset_symbol: str | None = Form(default=None),
    replace_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()

    # Check for duplicate content
    hash_result = await db.execute(
        select(Document).where(Document.content_hash == content_hash)
    )
    existing = hash_result.scalar_one_or_none()
    if existing and not replace_id:
        return JSONResponse(
            status_code=409,
            content={"existing_id": str(existing.id), "existing_filename": existing.filename},
        )

    # Handle replace: delete old document first
    if replace_id:
        old_result = await db.execute(
            select(Document).where(Document.id == uuid.UUID(replace_id))
        )
        old_doc = old_result.scalar_one_or_none()
        if old_doc:
            if old_doc.chroma_collection_id:
                try:
                    from app.services.rag_service import _get_client
                    client = _get_client()
                    client.delete_collection(old_doc.chroma_collection_id)
                except Exception:
                    pass
            if old_doc.file_path and Path(old_doc.file_path).exists():
                Path(old_doc.file_path).unlink()
            await db.delete(old_doc)
            await db.flush()

    UPLOAD_DIR = _upload_dir()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4()
    dest = UPLOAD_DIR / f"{doc_id}_{file.filename}"
    dest.write_bytes(content)

    asset_id = None
    if asset_symbol:
        from app.models.asset import Asset
        result = await db.execute(select(Asset).where(Asset.symbol == asset_symbol.upper()))
        asset = result.scalar_one_or_none()
        if asset:
            asset_id = asset.id

    doc = Document(
        id=doc_id,
        filename=file.filename,
        file_path=str(dest),
        asset_id=asset_id,
        content_hash=content_hash,
        status="pending",
    )
    db.add(doc)
    await db.commit()

    try:
        from arq.connections import ArqRedis, RedisSettings, create_pool
        from app.core.config import settings
        redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_ingest_document", str(doc_id))
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        job_id = None

    logger.info("document uploaded id=%s filename=%s", doc_id, file.filename)
    return {"document_id": str(doc_id), "status": "pending", "job_id": job_id}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
docker compose exec backend pytest tests/test_upload_dedup.py -v
```

Expected: `2 passed`

---

## Task 5: Frontend — duplicate modal + error state

**Files:**
- Modify: `frontend/app/(auth)/documents/page.tsx`

- [ ] **Step 1: Add state variables**

At the top of the `DocumentsPage` component, after the existing `useState` declarations, add:

```typescript
const [duplicateInfo, setDuplicateInfo] = useState<{ existing_id: string; existing_filename: string } | null>(null);
const [error, setError] = useState<string | null>(null);
```

- [ ] **Step 2: Update `load()` to show error state**

Replace the `load()` function:

```typescript
async function load() {
  setLoading(true);
  setError(null);
  try {
    const url = filter
      ? `/api/v1/documents?asset=${filter.toUpperCase()}`
      : "/api/v1/documents";
    const res = await api.get(url);
    if (res.ok) {
      setDocs(await res.json());
    } else {
      setError("Failed to load documents. Please try again.");
    }
  } catch {
    setError("Failed to load documents. Please try again.");
  } finally {
    setLoading(false);
  }
}
```

- [ ] **Step 3: Update `handleUpload()` to detect 409**

Replace the `handleUpload()` function:

```typescript
async function handleUpload(replaceId?: string) {
  const file = fileRef.current?.files?.[0];
  if (!file) return;
  setUploading(true);
  const form = new FormData();
  form.append("file", file);
  form.append("doc_type", docType);
  if (assetSymbol) form.append("asset_symbol", assetSymbol.toUpperCase());
  const url = replaceId
    ? `/api/v1/documents/upload?replace_id=${replaceId}`
    : "/api/v1/documents/upload";
  const res = await uploadWithAuth(url, form);
  setUploading(false);
  if (res.status === 409) {
    const data = await res.json();
    setDuplicateInfo(data);
    setUploadOpen(false);
    return;
  }
  setUploadOpen(false);
  setDuplicateInfo(null);
  load();
}
```

- [ ] **Step 4: Add duplicate confirmation dialog and error banner to JSX**

In the `return` block, after `<PageHeader title="Documents" />`, add the error banner:

```tsx
{error && (
  <div className="rounded-lg bg-[var(--color-danger-subtle)] border border-[var(--color-danger)] px-4 py-3 text-sm text-[var(--color-danger)]">
    {error}
  </div>
)}
```

After the upload `<Dialog>` closing tag (before the documents table card), add the duplicate confirmation dialog:

```tsx
<Dialog open={!!duplicateInfo} onOpenChange={(open) => { if (!open) setDuplicateInfo(null); }}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Duplicate File Detected</DialogTitle>
    </DialogHeader>
    <p className="text-sm text-[var(--color-text-secondary)] py-2">
      A file with identical content already exists as{" "}
      <span className="font-mono font-medium">{duplicateInfo?.existing_filename}</span>.
      Replace it with the new upload?
    </p>
    <div className="flex justify-end gap-2 pt-2">
      <Button variant="outline" onClick={() => setDuplicateInfo(null)}>
        Cancel
      </Button>
      <Button
        variant="destructive"
        disabled={uploading}
        onClick={() => {
          if (duplicateInfo) handleUpload(duplicateInfo.existing_id);
        }}
      >
        {uploading ? "Replacing…" : "Replace"}
      </Button>
    </div>
  </DialogContent>
</Dialog>
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Manual smoke test**

1. Navigate to `/documents` — page should load (or show error banner if API fails, not silent empty table).
2. Upload any file.
3. Upload the exact same file again — duplicate dialog should appear with the filename.
4. Click **Cancel** — dialog closes, no new record.
5. Upload the same file again, click **Replace** — old record is deleted, new one appears in the table.
