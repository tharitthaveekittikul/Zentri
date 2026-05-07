from app.core.logging import get_logger

logger = get_logger(__name__)

_THAI_TYPES = {"thai_stock", "thai_dr"}
_SUPPORTED_TYPES = {"us_stock", "etf", "thai_stock", "thai_dr"}


def get_logo_url(symbol: str, asset_type: str) -> str | None:
    if asset_type not in _SUPPORTED_TYPES:
        return None
    try:
        import yfinance as yf
        yf_symbol = f"{symbol}.BK" if asset_type in _THAI_TYPES else symbol
        info = yf.Ticker(yf_symbol).info
        website = info.get("website", "")
        if not website:
            return None
        domain = website.replace("https://", "").replace("http://", "").split("/")[0]
        url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        logger.info("Logo URL resolved: symbol=%s url=%s", symbol, url)
        return url
    except Exception:
        logger.warning("Failed to resolve logo for symbol=%s", symbol)
        return None
