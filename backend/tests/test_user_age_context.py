from datetime import date
from unittest.mock import patch

import pytest

from app.services.user_context import get_user_age_context


# Override the autouse setup_db fixture from conftest — this module is pure,
# no database access needed.
@pytest.fixture(autouse=True)
async def setup_db():
    yield


class FakeUser:
    def __init__(self, birth_date, plan_to_age):
        self.birth_date = birth_date
        self.plan_to_age = plan_to_age


def test_returns_none_when_no_birth_date():
    user = FakeUser(birth_date=None, plan_to_age=85)
    assert get_user_age_context(user) is None


def test_returns_none_when_plan_to_age_missing():
    user = FakeUser(birth_date=date(1990, 1, 1), plan_to_age=None)
    assert get_user_age_context(user) is None


def test_computes_age_correctly():
    with patch("app.services.user_context.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 5)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        user = FakeUser(birth_date=date(1994, 3, 10), plan_to_age=85)
        ctx = get_user_age_context(user)
    assert ctx["current_age"] == 32
    assert ctx["plan_to_age"] == 85
    assert ctx["years_remaining"] == 53
    assert ctx["target_year"] == 2079


def test_birthday_not_yet_this_year():
    with patch("app.services.user_context.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 5)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        user = FakeUser(birth_date=date(1994, 12, 1), plan_to_age=85)
        ctx = get_user_age_context(user)
    assert ctx["current_age"] == 31


def test_years_remaining_pre_birthday():
    with patch("app.services.user_context.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 5)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        user = FakeUser(birth_date=date(1994, 12, 1), plan_to_age=85)
        ctx = get_user_age_context(user)
    # born 1994-12-01, plan_to_age=85 → target_year=2079
    # today=2026-05-05 is pre-birthday (Dec 1 not yet reached)
    # years_remaining = 2079 - 2026 - 1 = 52 (subtract 1 because birthday hasn't occurred yet)
    assert ctx["current_age"] == 31
    assert ctx["years_remaining"] == 52
    assert ctx["target_year"] == 2079


def test_prompt_string_format():
    with patch("app.services.user_context.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 5)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        user = FakeUser(birth_date=date(1994, 3, 10), plan_to_age=85)
        ctx = get_user_age_context(user)
    assert ctx["prompt"] == "User context: age 32, planning horizon until age 85 (53 years remaining)."
