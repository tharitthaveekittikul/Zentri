import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/zentri_test"


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
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_setup_creates_user_and_returns_tokens(client):
    response = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "password123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_setup_returns_409_if_user_exists(client):
    await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "password123"},
    )
    response = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin2", "password": "password123"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_tokens(client):
    await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "password123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "password123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "password123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client):
    setup = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "password123"},
    )
    token = setup.json()["access_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_refresh_token_returns_401(client):
    setup = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "password123"},
    )
    refresh_token = setup.json()["refresh_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert response.status_code == 401
