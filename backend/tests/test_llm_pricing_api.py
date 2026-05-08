import pytest


@pytest.mark.anyio
async def test_get_llm_pricing_returns_all_models(client):
    r = await client.get("/api/v1/llm/pricing")
    assert r.status_code == 200
    data = r.json()
    assert "claude-sonnet-4-6" in data
    assert "gpt-4o" in data
    assert "gemini-2.5-pro" in data
    entry = data["claude-sonnet-4-6"]
    assert entry["input_per_mtoken"] == pytest.approx(3.0)
    assert entry["output_per_mtoken"] == pytest.approx(15.0)


@pytest.mark.anyio
async def test_get_llm_pricing_all_entries_have_positive_rates(client):
    r = await client.get("/api/v1/llm/pricing")
    assert r.status_code == 200
    for model, entry in r.json().items():
        assert entry["input_per_mtoken"] > 0, f"{model} input rate <= 0"
        assert entry["output_per_mtoken"] > 0, f"{model} output rate <= 0"
