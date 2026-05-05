import pytest


@pytest.mark.asyncio
async def test_get_calendar_empty(auth_client):
    response = await auth_client.get("/api/v1/dividends/calendar")
    assert response.status_code == 200
    assert response.json() == {"months": []}


@pytest.mark.asyncio
async def test_get_calendar_invalid_months(auth_client):
    response = await auth_client.get("/api/v1/dividends/calendar?months=0")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_upcoming_empty(auth_client):
    response = await auth_client.get("/api/v1/dividends/upcoming")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_confirm_nonexistent_event(auth_client):
    import uuid
    fake_id = str(uuid.uuid4())
    response = await auth_client.post(
        f"/api/v1/dividends/{fake_id}/confirm",
        json={"quantity": "10.0", "executed_at": "2026-05-15"},
    )
    assert response.status_code == 404
