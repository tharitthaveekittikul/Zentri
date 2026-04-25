import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_list_pipeline_jobs_empty(auth_client):
    response = await auth_client.get("/api/v1/pipeline/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_pipeline_job_not_found(auth_client):
    response = await auth_client.get(
        "/api/v1/pipeline/jobs/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_job_enqueues(auth_client):
    with patch("app.api.pipeline.create_pool") as mock_pool:
        mock_redis = AsyncMock()
        mock_pool.return_value = mock_redis
        mock_job = AsyncMock()
        mock_job.job_id = "test-job-id"
        mock_redis.enqueue_job.return_value = mock_job
        mock_redis.aclose = AsyncMock()

        response = await auth_client.post("/api/v1/pipeline/trigger/price_fetch_us")
        assert response.status_code == 202
        data = response.json()
        assert data["enqueued"] is True
        mock_redis.enqueue_job.assert_called_once_with("job_fetch_prices_us")
