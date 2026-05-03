"""
Override autouse DB fixture for pure unit tests in tests/core/.
These tests don't need a database connection.
"""
import pytest


@pytest.fixture(autouse=True)
async def setup_db():
    """No-op override: core unit tests do not need a DB."""
    yield
