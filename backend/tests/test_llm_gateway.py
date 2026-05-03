import pytest
from unittest.mock import AsyncMock, patch
from app.services.llm_gateway import LLMGateway, FEATURE_KEYS, DEFAULT_SYSTEM_PROMPTS, HUMAN_PROMPTS


def test_all_feature_keys_have_defaults():
    for key in FEATURE_KEYS:
        assert key in DEFAULT_SYSTEM_PROMPTS, f"Missing default system prompt for {key}"
        assert key in HUMAN_PROMPTS, f"Missing human prompt for {key}"


def test_human_prompt_has_placeholders():
    prompt = HUMAN_PROMPTS["import_template_generator"]
    assert "{file_format}" in prompt
    assert "{headers}" in prompt
    assert "{sample_rows}" in prompt


def test_human_prompt_classifier_has_placeholders():
    prompt = HUMAN_PROMPTS["transaction_classifier"]
    assert "{symbol}" in prompt
    assert "{exchange}" in prompt
    assert "{currency}" in prompt


@pytest.mark.asyncio
async def test_get_call_log_detail_404_for_unknown_id(auth_client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = await auth_client.get(f"/api/v1/llm/call-logs/{fake_id}")
    assert r.status_code == 404
