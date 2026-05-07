import pytest


@pytest.mark.asyncio
async def test_get_schedule_returns_6_defaults(auth_client):
    res = await auth_client.get("/api/v1/settings/schedule")
    assert res.status_code == 200
    configs = res.json()
    assert len(configs) == 6
    keys = {c["job_key"] for c in configs}
    assert keys == {"us_stock", "thai_stock", "thai_fund", "crypto", "gold", "benchmark"}


@pytest.mark.asyncio
async def test_get_schedule_us_stock_defaults(auth_client):
    res = await auth_client.get("/api/v1/settings/schedule")
    configs = {c["job_key"]: c for c in res.json()}
    us = configs["us_stock"]
    assert us["enabled"] is True
    assert us["days"] == [0, 1, 2, 3, 4]
    assert us["run_at_hour"] == 19
    assert us["run_at_minute"] == 0


@pytest.mark.asyncio
async def test_get_schedule_idempotent(auth_client):
    """Calling GET twice does not duplicate rows."""
    await auth_client.get("/api/v1/settings/schedule")
    res = await auth_client.get("/api/v1/settings/schedule")
    assert len(res.json()) == 6


@pytest.mark.asyncio
async def test_put_schedule_updates_config(auth_client):
    get_res = await auth_client.get("/api/v1/settings/schedule")
    configs = get_res.json()
    for c in configs:
        if c["job_key"] == "thai_stock":
            c["enabled"] = False
            c["run_at_hour"] = 10

    put_res = await auth_client.put("/api/v1/settings/schedule", json=configs)
    assert put_res.status_code == 200

    verify = await auth_client.get("/api/v1/settings/schedule")
    updated = {c["job_key"]: c for c in verify.json()}
    assert updated["thai_stock"]["enabled"] is False
    assert updated["thai_stock"]["run_at_hour"] == 10


@pytest.mark.asyncio
async def test_put_schedule_rejects_invalid_hour(auth_client):
    get_res = await auth_client.get("/api/v1/settings/schedule")
    configs = get_res.json()
    configs[0]["run_at_hour"] = 25  # invalid
    res = await auth_client.put("/api/v1/settings/schedule", json=configs)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_export_includes_schedule_configs(auth_client):
    # Seed defaults first
    await auth_client.get("/api/v1/settings/schedule")

    res = await auth_client.get("/api/v1/system/export")
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == "2"
    assert "schedule_configs" in data["settings"]
    assert len(data["settings"]["schedule_configs"]) == 6


@pytest.mark.asyncio
async def test_import_v1_backup_does_not_fail(auth_client):
    """v1 backup without schedule_configs imports successfully."""
    import json
    import io
    backup_v1 = {
        "version": "1",
        "exported_at": "2026-01-01T00:00:00Z",
        "settings": {
            "currency_primary": "THB",
            "currency_secondary": "USD",
        },
        "portfolio": {"holdings": [], "transactions": []},
    }
    file_content = json.dumps(backup_v1).encode()
    res = await auth_client.post(
        "/api/v1/system/import",
        files={"file": ("backup.json", io.BytesIO(file_content), "application/json")},
    )
    assert res.status_code == 200
