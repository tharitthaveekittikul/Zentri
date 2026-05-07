import os
import tempfile

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.main import app

_db_host = os.getenv("DB_TEST_HOST", "localhost")
TEST_DB_URL = f"postgresql+asyncpg://postgres:zentri-password-paotharit@{_db_host}:5432/zentri_test"
test_engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def set_upload_dir(tmp_path):
    os.environ["UPLOAD_DIR"] = str(tmp_path / "uploads")
    yield
    os.environ.pop("UPLOAD_DIR", None)


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    async with TestSession() as session:
        yield session


@pytest.fixture
async def client():
    async def override_get_db():
        async with TestSession() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client():
    async def override_get_db():
        async with TestSession() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        setup = await c.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": "password123"},
        )
        token = setup.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_finnomena_rows():
    return [
        {"Template": "Buy Note", "Fund_Code": "SCBSET50", "Trade_Date": "2026-04-27",
         "Total_Amount": "500", "Number_of_Units": "22.5926", "Filename": "confirmation.pdf"},
    ]

@pytest.fixture
def sample_dime_rows():
    return [
        {"type": "BUY", "symbol": "ABNB", "unit": "0.2889284", "price": "95.56",
         "currency": "USD", "settlement_date": "28/11/2022", "gross_ccy": "27.61",
         "fee_ccy": "0.00", "exchange_rate": "35.9775", "total_buy_thb": "993.34"},
    ]

@pytest.fixture
def sample_streaming_rows():
    return [
        {"type": "BUY", "share_name": "PTT", "unit": 100, "unit_price": 34.5,
         "net_amount": 3455.8, "trading_date": "30/09/2022"},
    ]
