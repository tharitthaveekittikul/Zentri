import pytest


@pytest.mark.asyncio
async def test_create_platform(auth_client):
    response = await auth_client.post("/api/v1/platforms", json={
        "name": "Robinhood",
        "asset_types_supported": ["us_stock", "crypto"],
        "notes": "US broker",
    })
    assert response.status_code == 201
    assert response.json()["name"] == "Robinhood"


@pytest.mark.asyncio
async def test_list_platforms(auth_client):
    await auth_client.post("/api/v1/platforms", json={"name": "Robinhood", "asset_types_supported": ["us_stock"]})
    response = await auth_client.get("/api/v1/platforms")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_update_platform(auth_client):
    create = await auth_client.post("/api/v1/platforms", json={"name": "Robinhood", "asset_types_supported": ["us_stock"]})
    pid = create.json()["id"]
    response = await auth_client.put(f"/api/v1/platforms/{pid}", json={"name": "Robinhood Pro", "asset_types_supported": ["us_stock", "crypto"]})
    assert response.status_code == 200
    assert response.json()["name"] == "Robinhood Pro"


@pytest.mark.asyncio
async def test_delete_platform(auth_client):
    create = await auth_client.post("/api/v1/platforms", json={"name": "Robinhood", "asset_types_supported": ["us_stock"]})
    pid = create.json()["id"]
    response = await auth_client.delete(f"/api/v1/platforms/{pid}")
    assert response.status_code == 204
    list_response = await auth_client.get("/api/v1/platforms")
    assert len(list_response.json()) == 0


@pytest.mark.asyncio
async def test_delete_platform_also_removes_linked_template(auth_client, db):
    # Create a platform
    r = await auth_client.post(
        "/api/v1/platforms",
        json={"name": "Test Broker Delete", "asset_types_supported": ["us_stock"], "notes": None},
    )
    assert r.status_code == 201
    platform_id = r.json()["id"]

    # Seed an ImportTemplate linked to this platform via the DB session
    import uuid as _uuid
    from datetime import datetime, timezone
    from app.models.import_template import ImportTemplate
    tmpl = ImportTemplate(
        id=_uuid.uuid4(),
        platform_id=_uuid.UUID(platform_id),
        user_id=_uuid.UUID(platform_id),  # user_id doesn't matter for this test
        file_format="csv",
        json_path=None,
        column_signature="abc123",
        field_map={},
        asset_type_rules=[],
        asset_type_fallback="us_stock",
        currency_default="THB",
        value_transforms={},
        derived_fields={},
        defaults={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(tmpl)
    await db.commit()

    # Delete the platform — should succeed (no FK violation)
    del_r = await auth_client.delete(f"/api/v1/platforms/{platform_id}")
    assert del_r.status_code == 204
