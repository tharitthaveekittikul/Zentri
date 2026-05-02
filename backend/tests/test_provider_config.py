import pytest


async def test_create_provider_config(auth_client):
    resp = await auth_client.post("/api/v1/provider-configs", json={
        "provider": "ollama",
        "host_url": "http://localhost:11434",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "ollama"
    assert data["is_connected"] is False
    assert "id" in data


async def test_create_provider_config_invalid_provider(auth_client):
    resp = await auth_client.post("/api/v1/provider-configs", json={
        "provider": "unknown_provider",
    })
    assert resp.status_code == 422


async def test_list_provider_configs(auth_client):
    await auth_client.post("/api/v1/provider-configs", json={"provider": "ollama", "host_url": "http://localhost:11434"})
    resp = await auth_client.get("/api/v1/provider-configs")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_delete_provider_config(auth_client):
    create = await auth_client.post("/api/v1/provider-configs", json={"provider": "ollama", "host_url": "http://localhost:11434"})
    pid = create.json()["id"]
    resp = await auth_client.delete(f"/api/v1/provider-configs/{pid}")
    assert resp.status_code == 204
