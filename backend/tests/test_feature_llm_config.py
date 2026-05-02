import pytest


async def test_create_feature_llm_config(auth_client):
    provider = await auth_client.post("/api/v1/provider-configs", json={
        "provider": "ollama", "host_url": "http://localhost:11434"
    })
    pid = provider.json()["id"]
    resp = await auth_client.post("/api/v1/feature-llm-configs", json={
        "feature_key": "import_template_generator",
        "provider_config_id": pid,
        "model": "llama3.2",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["feature_key"] == "import_template_generator"
    assert data["is_prompt_customized"] is False
    assert len(data["system_prompt"]) > 20


async def test_reset_to_default(auth_client):
    provider = await auth_client.post("/api/v1/provider-configs", json={
        "provider": "ollama", "host_url": "http://localhost:11434"
    })
    pid = provider.json()["id"]
    create = await auth_client.post("/api/v1/feature-llm-configs", json={
        "feature_key": "chat", "provider_config_id": pid, "model": "llama3.2",
    })
    cid = create.json()["id"]
    # Customize it
    await auth_client.patch(f"/api/v1/feature-llm-configs/{cid}", json={
        "system_prompt": "custom prompt", "model": "llama3.2"
    })
    # Reset
    resp = await auth_client.post(f"/api/v1/feature-llm-configs/{cid}/reset-prompt")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_prompt_customized"] is False
