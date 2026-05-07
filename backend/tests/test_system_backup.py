import json
import io
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


@pytest.mark.asyncio
async def test_export_returns_full_backup(auth_client):
    # seed a holding
    await auth_client.post("/api/v1/portfolio/holdings", json={
        "symbol": "AAPL", "asset_type": "us_stock", "quantity": "10",
        "avg_cost_price": "150", "currency": "USD",
    })

    response = await auth_client.get("/api/v1/system/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]

    data = response.json()
    assert data["version"] == "2"
    assert "exported_at" in data
    assert len(data["portfolio"]["holdings"]) == 1
    assert data["portfolio"]["holdings"][0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_import_replaces_all_data(auth_client):
    # Seed existing data that should be wiped
    seed_res = await auth_client.post("/api/v1/portfolio/holdings", json={
        "symbol": "OLD", "asset_type": "us_stock",
        "quantity": "5", "avg_cost_price": "100", "currency": "USD",
    })
    assert seed_res.status_code == 201

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
    backup = {"version": "99", "exported_at": "2026-01-01T00:00:00Z"}
    file_bytes = json.dumps(backup).encode()
    response = await auth_client.post(
        "/api/v1/system/import",
        files={"file": ("backup.json", io.BytesIO(file_bytes), "application/json")},
    )
    assert response.status_code == 400
    assert "version" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_export_import_encryption_round_trip(auth_client):
    """API keys must survive export (decrypted) → import (re-encrypted) intact."""
    from app.core.encryption import decrypt
    from sqlalchemy import select
    from app.models.provider_config import ProviderConfig

    # Create a provider config with a known API key via the API
    await auth_client.post("/api/v1/provider-configs", json={
        "provider": "anthropic",
        "api_key": "sk-test-key-12345",
    })

    # Export
    export_res = await auth_client.get("/api/v1/system/export")
    assert export_res.status_code == 200
    data = export_res.json()
    provider_configs = data.get("provider_configs", [])
    assert any(pc["provider"] == "anthropic" for pc in provider_configs), \
        "anthropic provider config should be in export"
    exported_key = next(pc["api_key"] for pc in provider_configs if pc["provider"] == "anthropic")
    assert exported_key == "sk-test-key-12345", "exported key must be plaintext"

    # Import (full replace with same data)
    import json, io
    file_bytes = json.dumps(data).encode()
    import_res = await auth_client.post(
        "/api/v1/system/import",
        files={"file": ("backup.json", io.BytesIO(file_bytes), "application/json")},
    )
    assert import_res.status_code == 200

    # Verify the key is re-encrypted in DB and decrypts back correctly
    # We do this by exporting again and checking the key is still correct
    re_export_res = await auth_client.get("/api/v1/system/export")
    assert re_export_res.status_code == 200
    re_data = re_export_res.json()
    re_configs = re_data.get("provider_configs", [])
    re_key = next((pc["api_key"] for pc in re_configs if pc["provider"] == "anthropic"), None)
    assert re_key == "sk-test-key-12345", "key must survive export→import→export round-trip"
