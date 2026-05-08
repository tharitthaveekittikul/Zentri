import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.llm_gateway import (
    FEATURE_KEYS,
    FEATURES_AGE_IN_HUMAN_PROMPT,
    FEATURES_WITH_AGE_CONTEXT,
    DEFAULT_SYSTEM_PROMPTS,
    HUMAN_PROMPTS,
    LLMGateway,
)
from app.services.llm_service import LLMResponse


def test_all_feature_keys_have_defaults():
    for key in FEATURE_KEYS:
        assert key in DEFAULT_SYSTEM_PROMPTS, f"Missing default system prompt for {key}"
        assert key in HUMAN_PROMPTS, f"Missing human prompt for {key}"


def test_human_prompt_has_placeholders():
    prompt = HUMAN_PROMPTS["import_translator"]
    assert "{file_format}" in prompt
    assert "{headers}" in prompt
    assert "{sample_rows}" in prompt


@pytest.mark.asyncio
async def test_get_call_log_detail_404_for_unknown_id(auth_client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = await auth_client.get(f"/api/v1/llm/call-logs/{fake_id}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Helpers / fake models
# ---------------------------------------------------------------------------

class FakeUser:
    def __init__(self, birth_date=None, plan_to_age=None, currency_primary="USD"):
        self.id = uuid.uuid4()
        self.birth_date = birth_date
        self.plan_to_age = plan_to_age
        self.currency_primary = currency_primary


def _make_feature_config(feature_key: str, provider_config_id: uuid.UUID):
    cfg = MagicMock()
    cfg.feature_key = feature_key
    cfg.provider_config_id = provider_config_id
    cfg.model = "gpt-4o-mini"
    cfg.system_prompt = None
    return cfg


def _make_provider(provider_config_id: uuid.UUID):
    p = MagicMock()
    p.id = provider_config_id
    p.provider = "openai"
    p.encrypted_api_key = None
    p.host_url = None
    p.is_connected = True
    return p


def _make_mock_db(user_row=None):
    """Return an AsyncMock DB session wired up for LLMGateway usage."""
    mock_db = AsyncMock()

    # scalar_one_or_none returns vary by query — use side_effect to handle order
    # _get_feature_config → scalar_one_or_none → FeatureLLMConfig
    # user row select → scalar_one_or_none → user_row
    # get_current_usd_thb (exchange rate select) → scalar_one_or_none → None
    provider_cfg_id = uuid.uuid4()

    async def execute_side_effect(stmt):
        result = AsyncMock()
        # We rely on call order: 1=feature_config, 2=provider, 3=user, 4=exchange_rate
        return result

    mock_db.execute = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    return mock_db, provider_cfg_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_gateway_deps():
    """Gateway with NO user row (anonymous / user not found)."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    provider_cfg_id = uuid.uuid4()
    feature_cfg = _make_feature_config("import_translator", provider_cfg_id)
    provider = _make_provider(provider_cfg_id)

    call_count = [0]

    async def execute_side_effect(stmt):
        call_count[0] += 1
        result = AsyncMock()
        n = call_count[0]
        if n == 1:
            result.scalar_one_or_none = MagicMock(return_value=feature_cfg)
        elif n == 2:
            result.scalar_one_or_none = MagicMock(return_value=provider)
        elif n == 3:
            # user row — None (no user)
            result.scalar_one_or_none = MagicMock(return_value=None)
        else:
            # exchange rate
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    mock_adapter = AsyncMock()
    fake_response = LLMResponse(content="ok", tokens_in=10, tokens_out=5, cost_usd=0.0001)
    mock_adapter.complete = AsyncMock(return_value=fake_response)

    gw = LLMGateway(mock_db)

    with patch("app.services.llm_gateway._build_adapter", return_value=mock_adapter), \
         patch("app.services.llm_gateway.decrypt", return_value="fake-key"):
        yield gw, mock_adapter, None


@pytest.fixture
def mock_gateway_deps_with_user():
    """Gateway with a user that HAS birth_date and plan_to_age set."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    provider_cfg_id = uuid.uuid4()
    provider = _make_provider(provider_cfg_id)

    user = FakeUser(
        birth_date=date(1990, 6, 15),
        plan_to_age=60,
        currency_primary="USD",
    )

    call_counts: dict = {}

    async def execute_side_effect(stmt):
        # We can't inspect stmt easily without imports, so use a per-test counter
        key = id(mock_db)
        call_counts[key] = call_counts.get(key, 0) + 1
        n = call_counts[key]
        result = AsyncMock()
        if n == 1:
            # _get_feature_config — we'll override per-test via the feature_cfg_holder
            result.scalar_one_or_none = MagicMock(return_value=execute_side_effect._feature_cfg)
        elif n == 2:
            result.scalar_one_or_none = MagicMock(return_value=provider)
        elif n == 3:
            result.scalar_one_or_none = MagicMock(return_value=user)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    execute_side_effect._feature_cfg = _make_feature_config("watchlist_scan", provider_cfg_id)
    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    mock_adapter = AsyncMock()
    fake_response = LLMResponse(content="ok", tokens_in=10, tokens_out=5, cost_usd=0.0001)
    mock_adapter.complete = AsyncMock(return_value=fake_response)

    gw = LLMGateway(mock_db)

    with patch("app.services.llm_gateway._build_adapter", return_value=mock_adapter), \
         patch("app.services.llm_gateway.decrypt", return_value="fake-key"):
        yield gw, mock_adapter, user


# ---------------------------------------------------------------------------
# Helper to reset call counter between tests that reuse the same fixture
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_current_date_always_injected(mock_gateway_deps):
    """current_date prefix appears in system prompt for every feature."""
    gw, mock_adapter, _ = mock_gateway_deps
    await gw.complete(
        "import_translator",
        uuid.uuid4(),
        {"file_format": "csv", "headers": "a,b", "sample_rows": "1,2"},
    )
    system_arg = mock_adapter.complete.call_args[0][0]
    assert "Current date:" in system_arg


@pytest.mark.asyncio
async def test_age_context_NOT_injected_for_import_translator(mock_gateway_deps_with_user):
    """import_translator must never receive age context."""
    gw, mock_adapter, user = mock_gateway_deps_with_user
    mock_db = gw._db

    provider_cfg_id = uuid.uuid4()
    provider = _make_provider(provider_cfg_id)
    feature_cfg = _make_feature_config("import_translator", provider_cfg_id)
    call_count = [0]

    async def execute_side_effect_import(stmt):
        call_count[0] += 1
        n = call_count[0]
        result = AsyncMock()
        if n == 1:
            result.scalar_one_or_none = MagicMock(return_value=feature_cfg)
        elif n == 2:
            result.scalar_one_or_none = MagicMock(return_value=provider)
        elif n == 3:
            result.scalar_one_or_none = MagicMock(return_value=user)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    mock_db.execute = AsyncMock(side_effect=execute_side_effect_import)

    await gw.complete(
        "import_translator",
        uuid.uuid4(),
        {"file_format": "csv", "headers": "a,b", "sample_rows": "1,2"},
    )
    system_arg = mock_adapter.complete.call_args[0][0]
    human_arg = mock_adapter.complete.call_args[0][1]
    assert "planning horizon" not in system_arg
    assert "planning horizon" not in human_arg


@pytest.mark.asyncio
async def test_age_context_in_system_for_watchlist_scan(mock_gateway_deps_with_user):
    """watchlist_scan gets age context in system prompt prefix."""
    gw, mock_adapter, user = mock_gateway_deps_with_user
    await gw.complete(
        "watchlist_scan",
        uuid.uuid4(),
        {"symbol": "AAPL", "prices_txt": "...", "rag_context": "..."},
    )
    system_arg = mock_adapter.complete.call_args[0][0]
    assert "planning horizon" in system_arg


@pytest.mark.asyncio
async def test_age_context_in_human_for_portfolio_analysis(mock_gateway_deps_with_user):
    """portfolio_analysis gets age context in human prompt, NOT system."""
    gw, mock_adapter, user = mock_gateway_deps_with_user
    mock_db = gw._db

    provider_cfg_id = uuid.uuid4()
    provider = _make_provider(provider_cfg_id)
    feature_cfg = _make_feature_config("portfolio_analysis", provider_cfg_id)
    call_count = [0]

    async def execute_side_effect_portfolio(stmt):
        call_count[0] += 1
        n = call_count[0]
        result = AsyncMock()
        if n == 1:
            result.scalar_one_or_none = MagicMock(return_value=feature_cfg)
        elif n == 2:
            result.scalar_one_or_none = MagicMock(return_value=provider)
        elif n == 3:
            result.scalar_one_or_none = MagicMock(return_value=user)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    mock_db.execute = AsyncMock(side_effect=execute_side_effect_portfolio)

    variables = {
        "holdings_table": "AAPL | 10 | 150 | 170 | 1700 | 50%",
        "cash_table": "USD | 1000 | 1000",
        "perf_1m": "5.2",
        "perf_3m": "12.1",
        "perf_ytd": "8.3",
        "total_value": "3400",
    }
    await gw.complete("portfolio_analysis", uuid.uuid4(), variables)
    system_arg = mock_adapter.complete.call_args[0][0]
    human_arg = mock_adapter.complete.call_args[0][1]
    assert "planning horizon" not in system_arg
    assert "planning until age" in human_arg


@pytest.mark.asyncio
async def test_primary_currency_formatted_in_system(mock_gateway_deps_with_user):
    """primary_currency variable replaces {primary_currency} in system prompt."""
    gw, mock_adapter, user = mock_gateway_deps_with_user
    user.currency_primary = "THB"
    mock_db = gw._db

    provider_cfg_id = uuid.uuid4()
    provider = _make_provider(provider_cfg_id)
    feature_cfg = _make_feature_config("portfolio_analysis", provider_cfg_id)
    call_count = [0]

    async def execute_side_effect_currency(stmt):
        call_count[0] += 1
        n = call_count[0]
        result = AsyncMock()
        if n == 1:
            result.scalar_one_or_none = MagicMock(return_value=feature_cfg)
        elif n == 2:
            result.scalar_one_or_none = MagicMock(return_value=provider)
        elif n == 3:
            result.scalar_one_or_none = MagicMock(return_value=user)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    mock_db.execute = AsyncMock(side_effect=execute_side_effect_currency)

    variables = {
        "holdings_table": "",
        "cash_table": "",
        "perf_1m": "0",
        "perf_3m": "0",
        "perf_ytd": "0",
        "total_value": "0",
    }
    await gw.complete("portfolio_analysis", user.id, variables)
    system_arg = mock_adapter.complete.call_args[0][0]
    assert "THB" in system_arg
    assert "{primary_currency}" not in system_arg
