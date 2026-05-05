import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def send_message(bot_token: str, chat_id: str, text: str) -> None:
    """Send a Telegram message. Raises RuntimeError on API failure."""
    url = _TELEGRAM_API.format(token=bot_token)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )
    if not resp.is_success:
        raise RuntimeError(f"Telegram API {resp.status_code}: {resp.text[:200]}")
    logger.info("Telegram message sent to chat %s", chat_id)
