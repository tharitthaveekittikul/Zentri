from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_events_calendar_returns_200(auth_client: AsyncClient):
    mock_result = {"months": []}
    with patch(
        "app.api.events.events_calendar.get_calendar",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await auth_client.get("/api/v1/events/calendar?months=3")
    assert response.status_code == 200
    data = response.json()
    assert "months" in data


@pytest.mark.asyncio
async def test_get_events_calendar_validates_months(auth_client: AsyncClient):
    response = await auth_client.get("/api/v1/events/calendar?months=0")
    assert response.status_code == 400

    response = await auth_client.get("/api/v1/events/calendar?months=13")
    assert response.status_code == 400
