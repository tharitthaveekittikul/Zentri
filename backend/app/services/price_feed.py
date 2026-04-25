from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import yfinance as yf
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.benchmark import Benchmark, BenchmarkPrice
from app.models.price import Price

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_decimal(val) -> Decimal | None:
    try:
        return Decimal(str(val)) if val is not None and str(val) != "nan" else None
    except Exception:
        return None


async def _upsert_prices(db: AsyncSession, rows: list[dict]) -> int:
    """Bulk upsert into the prices table. Returns count inserted."""
    if not rows:
        return 0
    await db.execute(
        text("""
            INSERT INTO prices (asset_id, timestamp, open, high, low, close, volume)
            VALUES (:asset_id, :timestamp, :open, :high, :low, :close, :volume)
            ON CONFLICT (asset_id, timestamp) DO UPDATE
            SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                close=EXCLUDED.close, volume=EXCLUDED.volume
        """),
        rows,
    )
    await db.commit()
    return len(rows)


async def _upsert_benchmark_prices(db: AsyncSession, rows: list[dict]) -> int:
    """Bulk upsert into benchmark_prices table."""
    if not rows:
        return 0
    await db.execute(
        text("""
            INSERT INTO benchmark_prices (benchmark_id, timestamp, open, high, low, close, volume)
            VALUES (:benchmark_id, :timestamp, :open, :high, :low, :close, :volume)
            ON CONFLICT (benchmark_id, timestamp) DO UPDATE
            SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                close=EXCLUDED.close, volume=EXCLUDED.volume
        """),
        rows,
    )
    await db.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# US Stocks
# ---------------------------------------------------------------------------

async def fetch_us_prices(db: AsyncSession) -> int:
    """Fetch latest daily OHLCV for all us_stock assets via yfinance."""
    result = await db.execute(
        select(Asset).where(Asset.asset_type == "us_stock")
    )
    assets = list(result.scalars().all())
    if not assets:
        logger.info("fetch_us_prices: no us_stock assets found")
        return 0

    symbols = [a.symbol for a in assets]
    asset_map = {a.symbol: a.id for a in assets}

    logger.info("fetch_us_prices: fetching %d symbols", len(symbols))

    def _fetch():
        tickers = yf.Tickers(" ".join(symbols))
        rows = []
        for sym, asset_id in asset_map.items():
            try:
                hist = tickers.tickers[sym].history(period="5d", interval="1d")
                for ts, row in hist.iterrows():
                    rows.append({
                        "asset_id": asset_id,
                        "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                        "open": _to_decimal(row.get("Open")),
                        "high": _to_decimal(row.get("High")),
                        "low": _to_decimal(row.get("Low")),
                        "close": _to_decimal(row.get("Close")),
                        "volume": _to_decimal(row.get("Volume")),
                    })
            except Exception as e:
                logger.warning("fetch_us_prices: failed for %s: %s", sym, e)
        return rows

    rows = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    inserted = await _upsert_prices(db, rows)
    logger.info("fetch_us_prices: upserted %d rows", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Crypto (CoinGecko)
# ---------------------------------------------------------------------------

COINGECKO_API = "https://api.coingecko.com/api/v3"


async def fetch_crypto_prices(db: AsyncSession) -> int:
    """Fetch latest prices for all crypto assets via CoinGecko.

    Expects asset.metadata_['coingecko_id'] to be set (e.g. 'bitcoin', 'ethereum').
    Assets without this field are skipped.
    """
    result = await db.execute(
        select(Asset).where(Asset.asset_type == "crypto")
    )
    assets = list(result.scalars().all())
    if not assets:
        logger.info("fetch_crypto_prices: no crypto assets found")
        return 0

    coin_map: dict[str, object] = {}
    for a in assets:
        cg_id = (a.metadata_ or {}).get("coingecko_id")
        if cg_id:
            coin_map[cg_id] = a
        else:
            logger.warning("fetch_crypto_prices: asset %s missing coingecko_id in metadata", a.symbol)

    if not coin_map:
        return 0

    ids_param = ",".join(coin_map.keys())
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{COINGECKO_API}/simple/price",
            params={"ids": ids_param, "vs_currencies": "usd", "include_last_updated_at": "true"},
        )
        resp.raise_for_status()
        data = resp.json()

    now = datetime.now(timezone.utc)
    rows = []
    for cg_id, price_data in data.items():
        asset = coin_map.get(cg_id)
        if not asset:
            continue
        rows.append({
            "asset_id": asset.id,
            "timestamp": now,
            "open": None,
            "high": None,
            "low": None,
            "close": _to_decimal(price_data.get("usd")),
            "volume": None,
        })

    inserted = await _upsert_prices(db, rows)
    logger.info("fetch_crypto_prices: upserted %d rows", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Gold
# ---------------------------------------------------------------------------

async def fetch_gold_price(db: AsyncSession) -> int:
    """Fetch gold spot price via yfinance (GC=F futures as proxy)."""
    result = await db.execute(
        select(Asset).where(Asset.asset_type == "gold")
    )
    assets = list(result.scalars().all())
    if not assets:
        logger.info("fetch_gold_price: no gold assets found")
        return 0

    def _fetch():
        ticker = yf.Ticker("GC=F")
        return ticker.history(period="5d", interval="1d")

    hist = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    if hist.empty:
        logger.warning("fetch_gold_price: yfinance returned empty history for GC=F")
        return 0

    rows = []
    for a in assets:
        for ts, row in hist.iterrows():
            rows.append({
                "asset_id": a.id,
                "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                "open": _to_decimal(row.get("Open")),
                "high": _to_decimal(row.get("High")),
                "low": _to_decimal(row.get("Low")),
                "close": _to_decimal(row.get("Close")),
                "volume": _to_decimal(row.get("Volume")),
            })

    inserted = await _upsert_prices(db, rows)
    logger.info("fetch_gold_price: upserted %d rows", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Benchmarks (S&P500 + SET)
# ---------------------------------------------------------------------------

BENCHMARK_YFINANCE_SYMBOLS = {
    "^GSPC": "^GSPC",
    "^SET.BK": "^SET.BK",
}


async def fetch_benchmark_prices(db: AsyncSession) -> int:
    """Fetch benchmark prices (S&P500 and SET) via yfinance."""
    result = await db.execute(select(Benchmark))
    benchmarks = list(result.scalars().all())
    if not benchmarks:
        logger.info("fetch_benchmark_prices: no benchmarks configured")
        return 0

    def _fetch(symbol: str):
        ticker = yf.Ticker(symbol)
        return ticker.history(period="5d", interval="1d")

    rows = []
    for bm in benchmarks:
        yf_sym = BENCHMARK_YFINANCE_SYMBOLS.get(bm.symbol, bm.symbol)
        hist = await asyncio.get_event_loop().run_in_executor(None, _fetch, yf_sym)
        if hist.empty:
            logger.warning("fetch_benchmark_prices: empty history for %s", bm.symbol)
            continue
        for ts, row in hist.iterrows():
            rows.append({
                "benchmark_id": bm.id,
                "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                "open": _to_decimal(row.get("Open")),
                "high": _to_decimal(row.get("High")),
                "low": _to_decimal(row.get("Low")),
                "close": _to_decimal(row.get("Close")),
                "volume": _to_decimal(row.get("Volume")),
            })

    inserted = await _upsert_benchmark_prices(db, rows)
    logger.info("fetch_benchmark_prices: upserted %d rows", inserted)
    return inserted
