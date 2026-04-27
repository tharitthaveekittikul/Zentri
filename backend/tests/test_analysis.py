import pytest
from httpx import AsyncClient


async def _create_aapl_asset(auth_client: AsyncClient) -> str:
    """Create AAPL asset and return its id."""
    res = await auth_client.post(
        "/api/v1/assets",
        json={"symbol": "AAPL", "asset_type": "us_stock", "name": "Apple Inc.", "currency": "USD"},
    )
    return res.json()["id"]


@pytest.mark.anyio
async def test_trigger_analysis_unknown_symbol_returns_404(auth_client: AsyncClient):
    resp = await auth_client.post("/api/v1/analysis/UNKNOWN_XYZ")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_latest_verdict_no_analysis_returns_404(auth_client: AsyncClient):
    # Create asset first, then check no analysis exists yet
    await _create_aapl_asset(auth_client)
    resp = await auth_client.get("/api/v1/analysis/AAPL/latest")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_trigger_analysis_returns_202(auth_client: AsyncClient):
    from unittest.mock import AsyncMock, patch
    await _create_aapl_asset(auth_client)
    with patch("arq.connections.create_pool") as mock_pool:
        mock_redis = AsyncMock()
        mock_job = AsyncMock()
        mock_job.job_id = "test-job-123"
        mock_redis.enqueue_job = AsyncMock(return_value=mock_job)
        mock_redis.aclose = AsyncMock()
        mock_pool.return_value = mock_redis

        resp = await auth_client.post("/api/v1/analysis/AAPL")
    assert resp.status_code == 202
    assert "job_id" in resp.json()
