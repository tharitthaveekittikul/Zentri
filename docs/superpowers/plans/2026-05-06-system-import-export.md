# System Import/Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full system backup/restore feature — export all user data to a versioned JSON file and import it back with a full replace, accessible from both the setup wizard and a dedicated settings page.

**Architecture:** A new `system_backup` service handles pure data serialization/deserialization, a new `system` API router exposes two endpoints (`GET /system/export`, `POST /system/import`), and the frontend adds a `/settings/backup` page plus a restore step in the setup wizard.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui, sonner toasts

---

## File Map

| Action | Path | Purpose |
|---|---|---|
| Create | `backend/app/schemas/system_backup.py` | Pydantic models for backup payload |
| Create | `backend/app/services/system_backup.py` | Export + import logic |
| Create | `backend/app/api/system.py` | Two API endpoints |
| Modify | `backend/app/main.py` | Register system router |
| Create | `backend/tests/test_system_backup.py` | Integration tests |
| Modify | `frontend/lib/api.ts` | Add `postForm` for multipart uploads |
| Create | `frontend/lib/services/system.ts` | `exportSystem` + `importSystem` |
| Create | `frontend/app/(auth)/settings/backup/page.tsx` | Backup & restore settings page |
| Modify | `frontend/app/setup/page.tsx` | Add restore step after account creation |
| Modify | `frontend/components/layout/Sidebar.tsx` | Add Backup nav link |

---

## Task 1: Backend — Pydantic backup schemas

**Files:**
- Create: `backend/app/schemas/system_backup.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_system_backup.py
import pytest
from datetime import datetime, timezone, date
from decimal import Decimal
from app.schemas.system_backup import SystemBackup, BackupSettings, BackupPortfolio


def test_system_backup_schema_round_trip():
    backup = SystemBackup(
        version="1",
        exported_at=datetime(2026, 5, 6, 0, 0, 0, tzinfo=timezone.utc),
        settings=BackupSettings(
            currency_primary="THB",
            currency_secondary="USD",
            birth_date=date(1990, 1, 1),
            plan_to_age=85,
            privacy_mode=False,
            telegram_chat_id=None,
            telegram_bot_token=None,
        ),
        portfolio=BackupPortfolio(holdings=[], transactions=[]),
        provider_configs=[],
        feature_llm_configs=[],
        watchlist=[],
        cash_balances=[],
        ai_analyses=[],
    )
    dumped = backup.model_dump()
    restored = SystemBackup.model_validate(dumped)
    assert restored.version == "1"
    assert restored.settings.currency_primary == "THB"
    assert restored.portfolio.holdings == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
python -m pytest tests/test_system_backup.py::test_system_backup_schema_round_trip -v
```

Expected: `ImportError` or `ModuleNotFoundError` — schema doesn't exist yet.

- [ ] **Step 3: Create the schema file**

```python
# backend/app/schemas/system_backup.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class BackupSettings(BaseModel):
    currency_primary: str
    currency_secondary: str
    birth_date: Optional[date] = None
    plan_to_age: Optional[int] = None
    privacy_mode: bool = False
    telegram_chat_id: Optional[str] = None
    telegram_bot_token: Optional[str] = None


class BackupHolding(BaseModel):
    symbol: str
    asset_type: str
    quantity: Decimal
    avg_cost_price: Decimal
    currency: str
    platform: Optional[str] = None
    purchased_at: Optional[date] = None


class BackupTransaction(BaseModel):
    symbol: str
    asset_type: str
    type: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    source: str
    executed_at: datetime
    platform: Optional[str] = None


class BackupPortfolio(BaseModel):
    holdings: list[BackupHolding] = []
    transactions: list[BackupTransaction] = []


class BackupProviderConfig(BaseModel):
    provider: str
    api_key: Optional[str] = None
    host_url: Optional[str] = None
    is_connected: bool = False


class BackupFeatureLLMConfig(BaseModel):
    feature_key: str
    provider: str
    model: str
    system_prompt: str
    is_prompt_customized: bool = False


class BackupWatchlistItem(BaseModel):
    symbol: str
    asset_type: str
    target_price: Optional[Decimal] = None
    currency: str = "USD"
    notes: Optional[str] = None
    alert_enabled: bool = True
    created_at: datetime


class BackupCashBalance(BaseModel):
    symbol: str
    asset_type: str = "cash"
    balance: float
    snapshot_date: date
    notes: Optional[str] = None


class BackupConversation(BaseModel):
    role: str
    content: str
    message_order: int


class BackupAIAnalysis(BaseModel):
    symbol: str
    verdict: str
    target_price: Optional[Decimal] = None
    reasoning: str
    provider: str
    model: str
    created_at: datetime
    conversations: list[BackupConversation] = []


class SystemBackup(BaseModel):
    version: str = "1"
    exported_at: datetime
    settings: BackupSettings
    portfolio: BackupPortfolio
    provider_configs: list[BackupProviderConfig] = []
    feature_llm_configs: list[BackupFeatureLLMConfig] = []
    watchlist: list[BackupWatchlistItem] = []
    cash_balances: list[BackupCashBalance] = []
    ai_analyses: list[BackupAIAnalysis] = []
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_system_backup.py::test_system_backup_schema_round_trip -v
```

Expected: `PASSED`

---

## Task 2: Backend — Export service

**Files:**
- Create: `backend/app/services/system_backup.py`

- [ ] **Step 1: Add export test**

Add to `backend/tests/test_system_backup.py`:

```python
@pytest.mark.asyncio
async def test_export_returns_full_backup(auth_client):
    # seed a holding
    asset = await auth_client.post("/api/v1/assets", json={
        "symbol": "AAPL", "asset_type": "us_stock", "name": "Apple", "currency": "USD"
    })
    asset_id = asset.json()["id"]
    await auth_client.post("/api/v1/portfolio/holdings", json={
        "asset_id": asset_id, "quantity": "10", "avg_cost_price": "150",
        "currency": "USD",
    })

    response = await auth_client.get("/api/v1/system/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]

    data = response.json()
    assert data["version"] == "1"
    assert "exported_at" in data
    assert len(data["portfolio"]["holdings"]) == 1
    assert data["portfolio"]["holdings"][0]["symbol"] == "AAPL"
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest tests/test_system_backup.py::test_export_returns_full_backup -v
```

Expected: `404` — endpoint doesn't exist yet.

- [ ] **Step 3: Create the export service function**

Create `backend/app/services/system_backup.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt
from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.asset import Asset
from app.models.cash_balance import CashBalance
from app.models.feature_llm_config import FeatureLLMConfig
from app.models.holding import Holding
from app.models.llm_conversation import LLMConversation
from app.models.provider_config import ProviderConfig
from app.models.transaction import Transaction
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.schemas.system_backup import (
    BackupAIAnalysis,
    BackupCashBalance,
    BackupConversation,
    BackupFeatureLLMConfig,
    BackupHolding,
    BackupPortfolio,
    BackupProviderConfig,
    BackupSettings,
    BackupTransaction,
    BackupWatchlistItem,
    SystemBackup,
)

logger = get_logger(__name__)

SUPPORTED_VERSIONS = {"1"}


async def export_backup(db: AsyncSession, user: User) -> SystemBackup:
    user_id = user.id

    # Settings
    settings = BackupSettings(
        currency_primary=user.currency_primary,
        currency_secondary=user.currency_secondary,
        birth_date=user.birth_date,
        plan_to_age=user.plan_to_age,
        privacy_mode=user.privacy_mode,
        telegram_chat_id=user.telegram_chat_id,
        telegram_bot_token=(
            decrypt(user.telegram_bot_token) if user.telegram_bot_token else None
        ),
    )

    # Holdings
    holdings_rows = await db.execute(
        select(Holding, Asset)
        .join(Asset, Asset.id == Holding.asset_id)
        .where(Holding.user_id == user_id)
    )
    holdings = [
        BackupHolding(
            symbol=asset.symbol,
            asset_type=asset.asset_type,
            quantity=holding.quantity,
            avg_cost_price=holding.avg_cost_price,
            currency=holding.currency,
            platform=holding.platform,
            purchased_at=holding.purchased_at,
        )
        for holding, asset in holdings_rows.all()
    ]

    # Transactions
    tx_rows = await db.execute(
        select(Transaction, Asset)
        .join(Asset, Asset.id == Transaction.asset_id)
        .where(Transaction.user_id == user_id)
    )
    transactions = [
        BackupTransaction(
            symbol=asset.symbol,
            asset_type=asset.asset_type,
            type=tx.type,
            quantity=tx.quantity,
            price=tx.price,
            fee=tx.fee,
            source=tx.source,
            executed_at=tx.executed_at,
            platform=tx.platform,
        )
        for tx, asset in tx_rows.all()
    ]

    # Provider configs
    pc_rows = await db.execute(
        select(ProviderConfig).where(ProviderConfig.user_id == user_id)
    )
    provider_configs = [
        BackupProviderConfig(
            provider=pc.provider,
            api_key=decrypt(pc.encrypted_api_key) if pc.encrypted_api_key else None,
            host_url=pc.host_url,
            is_connected=pc.is_connected,
        )
        for pc in pc_rows.scalars().all()
    ]

    # Feature LLM configs — resolve provider name via provider_config join
    flc_rows = await db.execute(
        select(FeatureLLMConfig, ProviderConfig)
        .join(ProviderConfig, ProviderConfig.id == FeatureLLMConfig.provider_config_id)
        .where(FeatureLLMConfig.user_id == user_id)
    )
    feature_llm_configs = [
        BackupFeatureLLMConfig(
            feature_key=flc.feature_key,
            provider=pc.provider,
            model=flc.model,
            system_prompt=flc.system_prompt,
            is_prompt_customized=flc.is_prompt_customized,
        )
        for flc, pc in flc_rows.all()
    ]

    # Watchlist
    wl_rows = await db.execute(
        select(WatchlistItem, Asset)
        .join(Asset, Asset.id == WatchlistItem.asset_id)
        .where(WatchlistItem.user_id == user_id)
    )
    watchlist = [
        BackupWatchlistItem(
            symbol=asset.symbol,
            asset_type=asset.asset_type,
            target_price=item.target_price,
            currency=item.currency,
            notes=item.notes,
            alert_enabled=item.alert_enabled,
            created_at=item.created_at,
        )
        for item, asset in wl_rows.all()
    ]

    # Cash balances
    cb_rows = await db.execute(
        select(CashBalance, Asset)
        .join(Asset, Asset.id == CashBalance.asset_id)
        .where(CashBalance.user_id == user_id)
    )
    cash_balances = [
        BackupCashBalance(
            symbol=asset.symbol,
            asset_type=asset.asset_type,
            balance=float(cb.balance),
            snapshot_date=cb.snapshot_date,
            notes=cb.notes,
        )
        for cb, asset in cb_rows.all()
    ]

    # AI analyses + conversations
    analysis_rows = await db.execute(
        select(AIAnalysis, Asset)
        .join(Asset, Asset.id == AIAnalysis.asset_id)
        .where(Asset.user_id == user_id)
    )
    ai_analyses = []
    for analysis, asset in analysis_rows.all():
        conv_rows = await db.execute(
            select(LLMConversation)
            .where(LLMConversation.analysis_id == analysis.id)
            .order_by(LLMConversation.message_order)
        )
        conversations = [
            BackupConversation(
                role=c.role, content=c.content, message_order=c.message_order
            )
            for c in conv_rows.scalars().all()
        ]
        ai_analyses.append(
            BackupAIAnalysis(
                symbol=asset.symbol,
                verdict=analysis.verdict,
                target_price=analysis.target_price,
                reasoning=analysis.reasoning,
                provider=analysis.provider,
                model=analysis.model,
                created_at=analysis.created_at,
                conversations=conversations,
            )
        )

    logger.info("Exported backup for user=%s", user_id)
    return SystemBackup(
        version="1",
        exported_at=datetime.now(timezone.utc),
        settings=settings,
        portfolio=BackupPortfolio(holdings=holdings, transactions=transactions),
        provider_configs=provider_configs,
        feature_llm_configs=feature_llm_configs,
        watchlist=watchlist,
        cash_balances=cash_balances,
        ai_analyses=ai_analyses,
    )
```

- [ ] **Step 4: Create the API file and register the router (needed to run the test)**

Create `backend/app/api/system.py`:

```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.user import User
from app.services import system_backup as backup_service

router = APIRouter(prefix="/system", tags=["system"])
logger = get_logger(__name__)


@router.get("/export")
async def export_system(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    backup = await backup_service.export_backup(db, current_user)
    filename = f"zentri-backup-{datetime.now().strftime('%Y-%m-%d')}.json"
    return JSONResponse(
        content=backup.model_dump(mode="json"),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/import", status_code=200)
async def import_system(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # placeholder — implemented in Task 3
    raise HTTPException(status_code=501, detail="Not implemented")
```

Add to `backend/app/main.py` imports and router registration:

```python
# In the import block, add:
from app.api import system

# After the last app.include_router line, add:
app.include_router(system.router, prefix="/api/v1")
```

- [ ] **Step 5: Run export test to verify it passes**

```bash
python -m pytest tests/test_system_backup.py::test_export_returns_full_backup -v
```

Expected: `PASSED`

---

## Task 3: Backend — Import service

**Files:**
- Modify: `backend/app/services/system_backup.py` (add `import_backup` function)
- Modify: `backend/app/api/system.py` (wire up import endpoint)

- [ ] **Step 1: Add import test**

Add to `backend/tests/test_system_backup.py`:

```python
import json

@pytest.mark.asyncio
async def test_import_replaces_all_data(auth_client):
    # Seed existing data that should be wiped
    asset = await auth_client.post("/api/v1/assets", json={
        "symbol": "OLD", "asset_type": "us_stock", "name": "Old Asset", "currency": "USD"
    })
    old_asset_id = asset.json()["id"]
    await auth_client.post("/api/v1/portfolio/holdings", json={
        "asset_id": old_asset_id, "quantity": "5", "avg_cost_price": "100", "currency": "USD",
    })

    # Build backup payload
    backup = {
        "version": "1",
        "exported_at": "2026-05-06T00:00:00Z",
        "settings": {
            "currency_primary": "USD",
            "currency_secondary": "EUR",
            "birth_date": None,
            "plan_to_age": 90,
            "privacy_mode": False,
            "telegram_chat_id": None,
            "telegram_bot_token": None,
        },
        "portfolio": {
            "holdings": [
                {
                    "symbol": "NVDA", "asset_type": "us_stock",
                    "quantity": "2", "avg_cost_price": "800",
                    "currency": "USD", "platform": None, "purchased_at": None,
                }
            ],
            "transactions": [],
        },
        "provider_configs": [],
        "feature_llm_configs": [],
        "watchlist": [],
        "cash_balances": [],
        "ai_analyses": [],
    }

    import io
    file_bytes = json.dumps(backup).encode()
    response = await auth_client.post(
        "/api/v1/system/import",
        files={"file": ("backup.json", io.BytesIO(file_bytes), "application/json")},
    )
    assert response.status_code == 200

    # Old data should be gone
    holdings = await auth_client.get("/api/v1/portfolio/holdings")
    symbols = [h["symbol"] for h in holdings.json()]
    assert "OLD" not in symbols
    assert "NVDA" in symbols

    # Settings should be updated
    display = await auth_client.get("/api/v1/settings/display")
    assert display.json()["currency_primary"] == "USD"


@pytest.mark.asyncio
async def test_import_rejects_unsupported_version(auth_client):
    import io, json
    backup = {"version": "99", "exported_at": "2026-01-01T00:00:00Z"}
    file_bytes = json.dumps(backup).encode()
    response = await auth_client.post(
        "/api/v1/system/import",
        files={"file": ("backup.json", io.BytesIO(file_bytes), "application/json")},
    )
    assert response.status_code == 400
    assert "version" in response.json()["detail"].lower()
```

- [ ] **Step 2: Run to verify both tests fail**

```bash
python -m pytest tests/test_system_backup.py::test_import_replaces_all_data tests/test_system_backup.py::test_import_rejects_unsupported_version -v
```

Expected: Both `FAILED` — endpoint returns 501.

- [ ] **Step 3: Add `import_backup` to the service**

Add to `backend/app/services/system_backup.py` (after the `export_backup` function):

```python
from app.core.encryption import decrypt, encrypt


async def _get_or_create_asset(
    db: AsyncSession, user_id: uuid.UUID, symbol: str, asset_type: str
) -> Asset:
    result = await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.symbol == symbol)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        asset = Asset(
            id=uuid.uuid4(),
            user_id=user_id,
            symbol=symbol,
            asset_type=asset_type,
            name=symbol,
            currency="USD",
            metadata_={},
        )
        db.add(asset)
        await db.flush()
    return asset


async def import_backup(db: AsyncSession, user: User, backup: SystemBackup) -> None:
    if backup.version not in SUPPORTED_VERSIONS:
        raise ValueError(f"Unsupported backup version: {backup.version}")

    user_id = user.id

    # --- Wipe (dependency order: most dependent first) ---
    # llm_conversations → ai_analyses → feature_llm_configs
    # → holdings/transactions/watchlist/cash_balances → assets → provider_configs
    from sqlalchemy import delete

    # Join-based deletes for tables without direct user_id
    analysis_ids_result = await db.execute(
        select(AIAnalysis.id)
        .join(Asset, Asset.id == AIAnalysis.asset_id)
        .where(Asset.user_id == user_id)
    )
    analysis_ids = [row[0] for row in analysis_ids_result.all()]
    if analysis_ids:
        await db.execute(
            delete(LLMConversation).where(LLMConversation.analysis_id.in_(analysis_ids))
        )
        await db.execute(
            delete(AIAnalysis).where(AIAnalysis.id.in_(analysis_ids))
        )

    await db.execute(delete(FeatureLLMConfig).where(FeatureLLMConfig.user_id == user_id))
    await db.execute(delete(WatchlistItem).where(WatchlistItem.user_id == user_id))
    await db.execute(delete(CashBalance).where(CashBalance.user_id == user_id))
    await db.execute(delete(Transaction).where(Transaction.user_id == user_id))
    await db.execute(delete(Holding).where(Holding.user_id == user_id))
    await db.execute(delete(Asset).where(Asset.user_id == user_id))
    await db.execute(delete(ProviderConfig).where(ProviderConfig.user_id == user_id))
    await db.flush()

    # --- Restore ---
    # Settings on user
    s = backup.settings
    user.currency_primary = s.currency_primary
    user.currency_secondary = s.currency_secondary
    user.birth_date = s.birth_date
    user.plan_to_age = s.plan_to_age
    user.privacy_mode = s.privacy_mode
    user.telegram_chat_id = s.telegram_chat_id
    user.telegram_bot_token = encrypt(s.telegram_bot_token) if s.telegram_bot_token else None

    # Provider configs — build a name→id map for feature config linking
    provider_name_to_id: dict[str, uuid.UUID] = {}
    for pc in backup.provider_configs:
        new_id = uuid.uuid4()
        db.add(ProviderConfig(
            id=new_id,
            user_id=user_id,
            provider=pc.provider,
            encrypted_api_key=encrypt(pc.api_key) if pc.api_key else None,
            host_url=pc.host_url,
            is_connected=pc.is_connected,
            models_cache=[],
        ))
        provider_name_to_id[pc.provider] = new_id
    await db.flush()

    # Holdings
    for h in backup.portfolio.holdings:
        asset = await _get_or_create_asset(db, user_id, h.symbol, h.asset_type)
        from datetime import datetime as dt, timezone as tz
        db.add(Holding(
            id=uuid.uuid4(),
            user_id=user_id,
            asset_id=asset.id,
            quantity=h.quantity,
            avg_cost_price=h.avg_cost_price,
            currency=h.currency,
            purchased_at=h.purchased_at,
            platform=h.platform,
            updated_at=dt.now(tz.utc),
        ))

    # Transactions
    for t in backup.portfolio.transactions:
        asset = await _get_or_create_asset(db, user_id, t.symbol, t.asset_type)
        db.add(Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            asset_id=asset.id,
            type=t.type,
            quantity=t.quantity,
            price=t.price,
            fee=t.fee,
            source=t.source,
            executed_at=t.executed_at,
            platform=t.platform,
        ))

    # Watchlist
    for w in backup.watchlist:
        asset = await _get_or_create_asset(db, user_id, w.symbol, w.asset_type)
        db.add(WatchlistItem(
            id=uuid.uuid4(),
            user_id=user_id,
            asset_id=asset.id,
            target_price=w.target_price,
            currency=w.currency,
            notes=w.notes,
            alert_enabled=w.alert_enabled,
            created_at=w.created_at,
        ))

    # Cash balances
    for cb in backup.cash_balances:
        asset = await _get_or_create_asset(db, user_id, cb.symbol, cb.asset_type)
        db.add(CashBalance(
            id=uuid.uuid4(),
            user_id=user_id,
            asset_id=asset.id,
            balance=cb.balance,
            snapshot_date=cb.snapshot_date,
            notes=cb.notes,
        ))

    # Feature LLM configs
    for flc in backup.feature_llm_configs:
        pc_id = provider_name_to_id.get(flc.provider)
        if pc_id is None:
            logger.warning("Skipping feature config %s — provider %s not found in backup", flc.feature_key, flc.provider)
            continue
        db.add(FeatureLLMConfig(
            id=uuid.uuid4(),
            user_id=user_id,
            feature_key=flc.feature_key,
            provider_config_id=pc_id,
            model=flc.model,
            system_prompt=flc.system_prompt,
            is_prompt_customized=flc.is_prompt_customized,
        ))

    # AI analyses + conversations
    for analysis in backup.ai_analyses:
        asset = await _get_or_create_asset(db, user_id, analysis.symbol, "us_stock")
        analysis_id = uuid.uuid4()
        db.add(AIAnalysis(
            id=analysis_id,
            asset_id=asset.id,
            verdict=analysis.verdict,
            target_price=analysis.target_price,
            reasoning=analysis.reasoning,
            provider=analysis.provider,
            model=analysis.model,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0,
            created_at=analysis.created_at,
        ))
        for conv in analysis.conversations:
            db.add(LLMConversation(
                id=uuid.uuid4(),
                analysis_id=analysis_id,
                role=conv.role,
                content=conv.content,
                message_order=conv.message_order,
            ))

    await db.commit()
    await db.refresh(user)
    logger.info("Import completed for user=%s", user_id)
```

- [ ] **Step 4: Wire up the import endpoint in `backend/app/api/system.py`**

Replace the placeholder import endpoint:

```python
@router.post("/import", status_code=200)
async def import_system(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import json
    try:
        raw = await file.read()
        data = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    version = data.get("version", "")
    if version not in backup_service.SUPPORTED_VERSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported backup version: {version}")

    try:
        from app.schemas.system_backup import SystemBackup
        backup = SystemBackup.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid backup format: {exc}")

    await backup_service.import_backup(db, current_user, backup)
    logger.info("System import completed for user=%s", current_user.id)
    return {"ok": True}
```

Also add the missing import at the top of `backend/app/api/system.py`:

```python
from app.schemas.system_backup import SystemBackup
```

- [ ] **Step 5: Run all backup tests**

```bash
python -m pytest tests/test_system_backup.py -v
```

Expected: All 4 tests `PASSED`

---

## Task 4: Frontend — Add `postForm` to api client

**Files:**
- Modify: `frontend/lib/api.ts`

The existing `api.post` always JSON-stringifies. File uploads need FormData with no `Content-Type` override (browser sets it with boundary automatically).

- [ ] **Step 1: Add `postForm` method to `frontend/lib/api.ts`**

Open `frontend/lib/api.ts`. After the `delete` line in the `api` export object, add:

```typescript
  postForm: (path: string, body: FormData) =>
    fetchWithAuth(path, {
      method: "POST",
      body,
      headers: {},  // override — don't set Content-Type so browser sets multipart boundary
    }),
```

The full `api` export should look like:

```typescript
export const api = {
  get: (path: string) => fetchWithAuth(path),
  post: (path: string, body: unknown) =>
    fetchWithAuth(path, { method: "POST", body: JSON.stringify(body) }),
  put: (path: string, body: unknown) =>
    fetchWithAuth(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: (path: string, body: unknown) =>
    fetchWithAuth(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (path: string) => fetchWithAuth(path, { method: "DELETE" }),
  postForm: (path: string, body: FormData) =>
    fetchWithAuth(path, { method: "POST", body, headers: {} }),
};
```

Note: `fetchWithAuth` merges `options.headers` into the default headers object. Passing `headers: {}` as an override prevents `Content-Type: application/json` from being set — required for multipart.

- [ ] **Step 2: Verify the `fetchWithAuth` headers merge handles empty headers correctly**

Read `frontend/lib/api.ts` lines 13–20. The merge is:
```typescript
const headers: Record<string, string> = {
  "Content-Type": "application/json",
  ...(options.headers as Record<string, string>),
};
```
Passing `headers: {}` spreads nothing, so `Content-Type: application/json` remains. To fix this properly, the `postForm` method must explicitly remove `Content-Type`. Update the implementation:

```typescript
  postForm: (path: string, body: FormData) => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(path, { method: "POST", body, headers });
  },
```

This bypasses `fetchWithAuth` entirely for form uploads. It does not retry on 401 — acceptable for this feature since the user is actively interacting.

---

## Task 5: Frontend — System API service

**Files:**
- Create: `frontend/lib/services/system.ts`

- [ ] **Step 1: Create the service file**

```typescript
// frontend/lib/services/system.ts
import { api } from "@/lib/api";

export async function exportSystem(): Promise<void> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch("/api/v1/system/export", { headers });
  if (!res.ok) throw new Error("Export failed");

  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename=(.+)/);
  const filename = match ? match[1] : "zentri-backup.json";

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function importSystem(file: File): Promise<void> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const form = new FormData();
  form.append("file", file);

  const res = await fetch("/api/v1/system/import", {
    method: "POST",
    headers,
    body: form,
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Import failed");
  }
}
```

---

## Task 6: Frontend — Backup settings page

**Files:**
- Create: `frontend/app/(auth)/settings/backup/page.tsx`

- [ ] **Step 1: Create the page**

```tsx
// frontend/app/(auth)/settings/backup/page.tsx
"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { exportSystem, importSystem } from "@/lib/services/system";

export default function BackupPage() {
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleExport() {
    setExporting(true);
    try {
      await exportSystem();
      toast.success("Backup downloaded");
    } catch {
      toast.error("Export failed. Check logs.");
    } finally {
      setExporting(false);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingFile(file);
    setConfirmOpen(true);
    e.target.value = "";
  }

  async function handleConfirmImport() {
    if (!pendingFile) return;
    setImporting(true);
    setConfirmOpen(false);
    try {
      await importSystem(pendingFile);
      toast.success("Restore complete. Refreshing...");
      setTimeout(() => window.location.reload(), 1500);
    } catch (e) {
      toast.error((e as Error).message || "Import failed");
    } finally {
      setImporting(false);
      setPendingFile(null);
    }
  }

  return (
    <div className="max-w-xl mx-auto space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold">Backup &amp; Restore</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Export all your data to a JSON file or restore from a previous backup.
        </p>
      </div>

      {/* Security warning */}
      <div className="rounded-lg border border-amber-400 bg-amber-50 dark:bg-amber-950/30 px-4 py-3 text-sm text-amber-800 dark:text-amber-300">
        <strong>Security notice:</strong> Backup files contain your API keys in plaintext. Do not share or store them in insecure locations.
      </div>

      {/* Export */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Export</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Downloads a <code className="text-xs bg-muted px-1 rounded">.json</code> file containing your portfolio, settings, AI configurations, watchlist, and AI analyses.
          </p>
          <Button onClick={handleExport} disabled={exporting}>
            {exporting ? "Exporting..." : "Download Backup"}
          </Button>
        </CardContent>
      </Card>

      {/* Import */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Restore</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Upload a backup file to restore your data. <strong>This will permanently replace all current data.</strong>
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={handleFileChange}
          />
          <Button
            variant="destructive"
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
          >
            {importing ? "Restoring..." : "Restore from Backup"}
          </Button>
        </CardContent>
      </Card>

      {/* Confirmation dialog */}
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Replace all data?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete all your current portfolio, settings, watchlist, and AI data, and replace it with the contents of{" "}
              <strong>{pendingFile?.name}</strong>. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPendingFile(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmImport}>
              Yes, restore
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
```

---

## Task 7: Frontend — Wizard restore step

**Files:**
- Modify: `frontend/app/setup/page.tsx`

The current wizard has 4 steps: `account → profile → hardware → llm`. We insert `restore` after `account`, making it 5 steps (20/40/60/80/100%).

- [ ] **Step 1: Update `Step` type and add restore state**

In `frontend/app/setup/page.tsx`, find:

```typescript
type Step = "account" | "profile" | "hardware" | "llm";
```

Replace with:

```typescript
type Step = "account" | "restore" | "profile" | "hardware" | "llm";
```

In the component body, add new state after the existing state declarations:

```typescript
const [restoreFile, setRestoreFile] = useState<File | null>(null);
const [restoreError, setRestoreError] = useState<string | null>(null);
```

- [ ] **Step 2: Change account step to go to restore next**

Find the line where the account step transitions:

```typescript
setStep("profile");
```

Replace with:

```typescript
setStep("restore");
```

Update the progress text in the account step card. Find:

```
Step 1 of 4 — Create your account
```

Replace with:

```
Step 1 of 5 — Create your account
```

And the `Progress value={25}` to `value={20}`.

- [ ] **Step 3: Update remaining step progress values**

In the profile step:
- `Step 2 of 4 — Optional` → `Step 3 of 5 — Optional`  
- `Progress value={50}` → `value={60}`

In the hardware step:
- `Step 3 of 4` → `Step 4 of 5`
- `Progress value={75}` → `value={80}`

In the final (llm/complete) step:
- `Step 4 of 4` → `Step 5 of 5`
- `Progress value={100}` stays `100`

- [ ] **Step 4: Add the restore step UI**

Import `importSystem` at the top of the file:

```typescript
import { importSystem } from "@/lib/services/system";
```

Add the restore step render block before the profile step (find `if (step === "profile")` and insert before it):

```tsx
if (step === "restore") {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Restore from backup?</CardTitle>
          <p className="text-sm text-muted-foreground">Step 2 of 5 — Optional</p>
          <Progress value={40} className="mt-2" />
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            If you have a Zentri backup file, upload it now to restore all your data and skip the remaining setup steps.
          </p>
          {restoreError && (
            <p className="text-sm text-destructive">{restoreError}</p>
          )}
          <div className="flex gap-2">
            <label className="flex-1">
              <input
                type="file"
                accept=".json"
                className="hidden"
                disabled={loading}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  setRestoreFile(file);
                  setLoading(true);
                  setRestoreError(null);
                  try {
                    await importSystem(file);
                    router.push("/");
                  } catch (err) {
                    setRestoreError((err as Error).message || "Restore failed");
                    setRestoreFile(null);
                  } finally {
                    setLoading(false);
                  }
                  e.target.value = "";
                }}
              />
              <Button asChild className="w-full" disabled={loading}>
                <span>{loading ? "Restoring..." : "Upload backup file"}</span>
              </Button>
            </label>
            <Button
              variant="outline"
              className="flex-1"
              disabled={loading}
              onClick={() => setStep("profile")}
            >
              Start fresh
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

---

## Task 8: Frontend — Add Backup nav link

**Files:**
- Modify: `frontend/components/layout/Sidebar.tsx`

- [ ] **Step 1: Add import and nav item**

In `frontend/components/layout/Sidebar.tsx`, find the lucide-react import block and add `HardDrive` to the import:

```typescript
import {
  LayoutDashboard,
  Briefcase,
  Star,
  TrendingUp,
  CalendarDays,
  Receipt,
  FileText,
  Activity,
  Bot,
  Settings,
  Upload,
  HardDrive,
} from "lucide-react";
```

In `navItems`, add the Backup entry after the Settings entry:

```typescript
  { href: "/settings/backup", label: "Backup", icon: HardDrive },
```

The full `navItems` array:

```typescript
const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/net-worth", label: "Net Worth", icon: TrendingUp },
  { href: "/dividends", label: "Dividends", icon: CalendarDays },
  { href: "/transactions", label: "Transactions", icon: Receipt },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/pipeline", label: "Pipeline", icon: Activity },
  { href: "/import", label: "Import", icon: Upload },
  { href: "/ai-usage", label: "AI Usage", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/settings/backup", label: "Backup", icon: HardDrive },
];
```

---

## Verification Checklist

- [ ] All 4 backend tests pass: `python -m pytest tests/test_system_backup.py -v`
- [ ] Export downloads a valid JSON file with all sections populated
- [ ] Import wipes old data and restores from file (test manually by exporting, adding dummy data, then importing)
- [ ] Import with wrong version returns a 400 with "version" in the error message
- [ ] Settings backup page renders at `/settings/backup`
- [ ] Export button downloads the file
- [ ] Restore button shows confirmation dialog before proceeding
- [ ] After import, page reloads and shows restored data
- [ ] Wizard shows restore step as Step 2 of 5 after account creation
- [ ] Uploading a backup in wizard redirects to `/` (dashboard)
- [ ] "Start fresh" in wizard proceeds to profile step
- [ ] Sidebar shows "Backup" link pointing to `/settings/backup`
