import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_llm_settings_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/settings/llm")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_upsert_llm_settings_ollama(auth_client: AsyncClient):
    resp = await auth_client.put(
        "/api/v1/settings/llm",
        json={"provider": "ollama", "model": "llama3.2"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    settings = await auth_client.get("/api/v1/settings/llm")
    data = settings.json()
    assert len(data) == 1
    assert data[0]["provider"] == "ollama"
    assert data[0]["is_active"] is True
    assert data[0]["masked_key"] is None


@pytest.mark.anyio
async def test_upsert_llm_settings_claude_masks_key(auth_client: AsyncClient):
    resp = await auth_client.put(
        "/api/v1/settings/llm",
        json={"provider": "claude", "model": "claude-sonnet-4-6", "api_key": "sk-ant-api03-secretkey"},
    )
    assert resp.status_code == 200

    settings = await auth_client.get("/api/v1/settings/llm")
    data = settings.json()
    provider = next(d for d in data if d["provider"] == "claude")
    assert "sk-ant-a" in provider["masked_key"]
    assert "secretkey" not in provider["masked_key"]
    assert "****" in provider["masked_key"]


@pytest.mark.anyio
async def test_only_one_provider_active_at_a_time(auth_client: AsyncClient):
    await auth_client.put("/api/v1/settings/llm", json={"provider": "ollama", "model": "llama3.2"})
    await auth_client.put(
        "/api/v1/settings/llm",
        json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-openai-key"},
    )
    settings = await auth_client.get("/api/v1/settings/llm")
    active = [d for d in settings.json() if d["is_active"]]
    assert len(active) == 1
    assert active[0]["provider"] == "openai"
