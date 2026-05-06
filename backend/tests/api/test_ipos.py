import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_analyze_ipo_not_found(auth_client: AsyncClient):
    fake_id = str(uuid.uuid4())
    with patch("app.api.ipos.ipo_feed.get_event", new=AsyncMock(return_value=None)):
        response = await auth_client.post(f"/api/v1/ipos/{fake_id}/analyze")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_analyze_ipo_llm_not_configured(auth_client: AsyncClient):
    fake_event = MagicMock()
    fake_event.id = uuid.uuid4()
    fake_event.symbol = "ACME"
    fake_event.company_name = "Acme Corp"
    fake_event.sector = "Technology"
    fake_event.ipo_date = date(2026, 7, 1)
    fake_event.price_low = None
    fake_event.price_high = None

    with (
        patch("app.api.ipos.ipo_feed.get_event", new=AsyncMock(return_value=fake_event)),
        patch("app.api.ipos._get_cached_analysis", new=AsyncMock(return_value=None)),
        patch(
            "app.api.ipos.LLMGateway.complete",
            side_effect=ValueError("No LLM config for feature 'ipo_analysis'"),
        ),
    ):
        response = await auth_client.post(f"/api/v1/ipos/{fake_event.id}/analyze")
    assert response.status_code == 400
    assert "Settings" in response.json()["detail"]
