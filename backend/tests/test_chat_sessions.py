# backend/tests/test_chat_sessions.py
import asyncio

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "postgresql+asyncpg://postgres:zentri-password-paotharit@localhost:5432/zentri_test"


@pytest.fixture
async def setup_test_db():
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(setup_test_db):
    engine = setup_test_db
    TestSession = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_token(client):
    await client.post("/api/v1/auth/setup", json={"username": "admin", "password": "pw123"})
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "pw123"})
    return r.json()["access_token"]


@pytest.fixture
async def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.mark.asyncio
async def test_create_session_returns_id_and_title(client, headers):
    r = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "What's my portfolio worth?"},
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["id"]
    assert data["title"] == "What's my portfolio worth?"


@pytest.mark.asyncio
async def test_create_session_truncates_long_title(client, headers):
    long_title = "x" * 100
    r = await client.post(
        "/api/v1/chat/sessions",
        json={"title": long_title},
        headers=headers,
    )
    assert r.status_code == 201
    assert len(r.json()["title"]) == 60


@pytest.mark.asyncio
async def test_list_sessions_returns_most_recent_first(client, headers):
    await client.post("/api/v1/chat/sessions", json={"title": "First"}, headers=headers)
    await asyncio.sleep(0.01)
    await client.post("/api/v1/chat/sessions", json={"title": "Second"}, headers=headers)
    r = await client.get("/api/v1/chat/sessions", headers=headers)
    assert r.status_code == 200
    titles = [s["title"] for s in r.json()]
    assert titles[0] == "Second"


@pytest.mark.asyncio
async def test_rename_session(client, headers):
    create_r = await client.post(
        "/api/v1/chat/sessions", json={"title": "Old Title"}, headers=headers
    )
    session_id = create_r.json()["id"]
    r = await client.patch(
        f"/api/v1/chat/sessions/{session_id}",
        json={"title": "New Title"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["title"] == "New Title"


@pytest.mark.asyncio
async def test_get_messages_empty_for_new_session(client, headers):
    create_r = await client.post(
        "/api/v1/chat/sessions", json={"title": "Empty"}, headers=headers
    )
    session_id = create_r.json()["id"]
    r = await client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_session_not_found_returns_404(client, headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = await client.get(f"/api/v1/chat/sessions/{fake_id}/messages", headers=headers)
    assert r.status_code == 404
