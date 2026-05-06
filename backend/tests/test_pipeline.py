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


@pytest.mark.asyncio
async def test_create_and_finish_step(db):
    from app.services.pipeline import create_log, create_step, finish_step

    log = await create_log(db, "price_fetch_us")
    step = await create_step(db, log.id, "fetch_and_store")
    assert step.status == "running"
    assert step.finished_at is None

    finished = await finish_step(db, step, success=True, metadata={"inserted": 42})
    assert finished.status == "done"
    assert finished.step_metadata == {"inserted": 42}
    assert finished.finished_at is not None


@pytest.mark.asyncio
async def test_list_logs_includes_steps(db):
    from app.services.pipeline import create_log, create_step, list_logs

    log = await create_log(db, "price_fetch_us")
    await create_step(db, log.id, "fetch_and_store")

    logs = await list_logs(db, limit=10)
    assert any(str(l.id) == str(log.id) for l in logs)
    matching = next(l for l in logs if str(l.id) == str(log.id))
    assert len(matching.steps) == 1
    assert matching.steps[0].step_name == "fetch_and_store"
