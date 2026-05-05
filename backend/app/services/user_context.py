import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


def get_user_age_context(user: Any) -> dict | None:
    if not user.birth_date or user.plan_to_age is None:
        return None

    today = date.today()
    had_birthday = (today.month, today.day) >= (user.birth_date.month, user.birth_date.day)
    current_age = today.year - user.birth_date.year - (0 if had_birthday else 1)
    target_year = user.birth_date.year + user.plan_to_age
    years_remaining = target_year - today.year - (0 if had_birthday else 1)

    logger.debug("User age context: age=%d plan_to_age=%d", current_age, user.plan_to_age)

    return {
        "current_age": current_age,
        "plan_to_age": user.plan_to_age,
        "years_remaining": years_remaining,
        "target_year": target_year,
        "prompt": (
            f"User context: age {current_age}, planning horizon until age "
            f"{user.plan_to_age} ({years_remaining} years remaining)."
        ),
    }
