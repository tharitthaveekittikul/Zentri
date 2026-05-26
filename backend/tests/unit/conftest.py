import pytest


@pytest.fixture(autouse=True)
async def setup_db():
    yield
