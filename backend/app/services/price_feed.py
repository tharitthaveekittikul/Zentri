from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import yfinance as yf
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.transaction import Transaction
from app.models.benchmark import Benchmark, BenchmarkPrice
from app.models.price import Price
from app.models.user import User

SEC_BASE_URL = "https://api.sec.or.th"

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

async def fetch_us_prices(db: AsyncSession) -> dict:
    """Fetch latest daily OHLCV for all us_stock and etf assets via yfinance."""
    result = await db.execute(
        select(Asset).where(Asset.asset_type.in_(["us_stock", "etf"]))
    )
    assets = list(result.scalars().all())
    if not assets:
        logger.info("fetch_us_prices: no us_stock assets found")
        return {"inserted": 0, "symbols": 0, "tickers": []}

    symbols = [a.symbol for a in assets]
    asset_map = {a.symbol: a.id for a in assets}

    logger.info("fetch_us_prices: fetching %d symbols", len(symbols))

    def _fetch():
        tickers = yf.Tickers(" ".join(symbols))
        rows = []
        fetched = []
        for sym, asset_id in asset_map.items():
            try:
                hist = tickers.tickers[sym].history(period="5d", interval="1d")
                if not hist.empty:
                    fetched.append(sym)
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
        return rows, fetched

    rows, fetched_symbols = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    inserted = await _upsert_prices(db, rows)
    logger.info("fetch_us_prices: upserted %d rows for %d symbols", inserted, len(fetched_symbols))
    return {"table": "prices", "inserted": inserted, "symbols": len(fetched_symbols), "tickers": fetched_symbols}


# ---------------------------------------------------------------------------
# Thai Stocks + Thai DRs (SET via yfinance, .BK suffix)
# ---------------------------------------------------------------------------

async def fetch_thai_stock_prices(db: AsyncSession) -> dict:
    """Fetch latest daily OHLCV for all thai_stock and thai_dr assets via yfinance.

    Appends .BK suffix to each symbol to form the SET ticker (e.g. PTT → PTT.BK).
    """
    result = await db.execute(
        select(Asset).where(Asset.asset_type.in_(["thai_stock", "thai_dr"]))
    )
    assets = list(result.scalars().all())
    if not assets:
        logger.info("fetch_thai_stock_prices: no thai_stock/thai_dr assets found")
        return {"inserted": 0, "symbols": 0, "tickers": []}

    asset_map = {f"{a.symbol}.BK": a.id for a in assets}
    yf_symbols = list(asset_map.keys())

    logger.info("fetch_thai_stock_prices: fetching %d symbols", len(yf_symbols))

    def _fetch():
        tickers = yf.Tickers(" ".join(yf_symbols))
        rows = []
        fetched = []
        for yf_sym, asset_id in asset_map.items():
            try:
                hist = tickers.tickers[yf_sym].history(period="5d", interval="1d")
                if not hist.empty:
                    fetched.append(yf_sym)
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
                logger.warning("fetch_thai_stock_prices: failed for %s: %s", yf_sym, e)
        return rows, fetched

    rows, fetched_symbols = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    inserted = await _upsert_prices(db, rows)
    logger.info("fetch_thai_stock_prices: upserted %d rows for %d symbols", inserted, len(fetched_symbols))
    return {"table": "prices", "inserted": inserted, "symbols": len(fetched_symbols), "tickers": fetched_symbols}


# ---------------------------------------------------------------------------
# Crypto (CoinGecko)
# ---------------------------------------------------------------------------

COINGECKO_API = "https://api.coingecko.com/api/v3"


async def fetch_crypto_prices(db: AsyncSession) -> dict:
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
        return {"inserted": 0, "coins": []}

    coin_map: dict[str, object] = {}
    for a in assets:
        cg_id = (a.metadata_ or {}).get("coingecko_id")
        if cg_id:
            coin_map[cg_id] = a
        else:
            logger.warning("fetch_crypto_prices: asset %s missing coingecko_id in metadata", a.symbol)

    if not coin_map:
        return {"inserted": 0, "coins": []}

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
    coin_prices = {}
    for cg_id, price_data in data.items():
        asset = coin_map.get(cg_id)
        if not asset:
            continue
        usd_price = price_data.get("usd")
        coin_prices[asset.symbol] = usd_price
        rows.append({
            "asset_id": asset.id,
            "timestamp": now,
            "open": None,
            "high": None,
            "low": None,
            "close": _to_decimal(usd_price),
            "volume": None,
        })

    inserted = await _upsert_prices(db, rows)
    logger.info("fetch_crypto_prices: upserted %d rows", inserted)
    return {"table": "prices", "inserted": inserted, "coins": [f"{sym} ${price}" for sym, price in coin_prices.items()]}


# ---------------------------------------------------------------------------
# Gold
# ---------------------------------------------------------------------------

async def fetch_gold_price(db: AsyncSession) -> dict:
    """Fetch gold spot price via yfinance (GC=F futures as proxy)."""
    result = await db.execute(
        select(Asset).where(Asset.asset_type == "gold")
    )
    assets = list(result.scalars().all())
    if not assets:
        logger.info("fetch_gold_price: no gold assets found")
        return {"inserted": 0}

    def _fetch():
        ticker = yf.Ticker("GC=F")
        return ticker.history(period="5d", interval="1d")

    hist = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    if hist.empty:
        logger.warning("fetch_gold_price: yfinance returned empty history for GC=F")
        return {"inserted": 0}

    latest_close = _to_decimal(hist.iloc[-1].get("Close")) if not hist.empty else None

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
    result_meta = {"table": "prices", "inserted": inserted}
    if latest_close is not None:
        result_meta["latest_close"] = float(latest_close)
    return result_meta


# ---------------------------------------------------------------------------
# Benchmarks (S&P500 + SET)
# ---------------------------------------------------------------------------

BENCHMARK_YFINANCE_SYMBOLS = {
    "^GSPC": "^GSPC",
    "^SET.BK": "^SET.BK",
}


async def fetch_benchmark_prices(db: AsyncSession, period: str = "5d") -> int:
    """Fetch benchmark prices (S&P500 and SET) via yfinance."""
    result = await db.execute(select(Benchmark))
    benchmarks = list(result.scalars().all())
    if not benchmarks:
        logger.info("fetch_benchmark_prices: no benchmarks configured")
        return 0

    def _fetch(symbol: str):
        ticker = yf.Ticker(symbol)
        return ticker.history(period=period, interval="1d")

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
    return {"table": "benchmark_prices", "inserted": inserted, "benchmarks": [bm.symbol for bm in benchmarks]}


# ---------------------------------------------------------------------------
# Thai Mutual Funds (SEC Thailand API v2)
# ---------------------------------------------------------------------------

async def _fetch_th_fund_for_user(
    client: httpx.AsyncClient,
    assets: list,
    api_key: str,
    today: str,
) -> tuple[list[dict], list[str], list[str]]:
    """Fetch NAV rows for a single user's th_fund assets. Returns (rows, fetched, skipped)."""
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }
    rows: list[dict] = []
    fetched: list[str] = []
    skipped: list[str] = []

    for asset in assets:
        proj_id = (asset.metadata_ or {}).get("proj_id")
        if not proj_id:
            logger.warning("fetch_th_fund_prices: asset %s missing proj_id in metadata", asset.symbol)
            skipped.append(asset.symbol)
            continue

        start_date = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
        params: dict = {
            "proj_id": proj_id,
            "start_nav_date": start_date,
            "end_nav_date": today,
            "page_size": 100,
        }
        fund_class = (asset.metadata_ or {}).get("fund_class_name")
        if fund_class:
            params["fund_class_name"] = fund_class

        try:
            resp = await client.get(
                f"{SEC_BASE_URL}/v2/fund/daily-info/nav",
                headers=headers,
                params=params,
            )
            if resp.status_code == 204:
                logger.info("fetch_th_fund_prices: no NAV for %s in last 14 days", proj_id)
                continue
            resp.raise_for_status()
            data = resp.json()

            valid_items = [
                item for item in data.get("items", [])
                if item.get("last_val") and item.get("nav_date")
            ]
            if fund_class:
                valid_items = [i for i in valid_items if i.get("fund_class_name") == fund_class]
            if not valid_items:
                continue
            latest = max(valid_items, key=lambda x: x["nav_date"])
            nav_val = _to_decimal(latest["last_val"])
            nav_dt = datetime.strptime(latest["nav_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            rows.append({
                "asset_id": asset.id,
                "timestamp": nav_dt,
                "open": None,
                "high": None,
                "low": None,
                "close": nav_val,
                "volume": None,
            })
            fetched.append(asset.symbol)
            logger.debug("fetch_th_fund_prices: %s nav_date=%s last_val=%s", asset.symbol, latest["nav_date"], nav_val)

            await asyncio.sleep(0.01)  # 10ms between calls per SEC rate limit guidance
        except Exception as e:
            logger.warning("fetch_th_fund_prices: failed for %s (%s): %s", asset.symbol, proj_id, e)

    return rows, fetched, skipped


async def fetch_th_fund_prices(db: AsyncSession) -> dict:
    """Fetch daily NAV for all th_fund assets via SEC Thailand Open API v2.

    Iterates per user — each user must have sec_api_key configured in settings.
    Requires asset.metadata_['proj_id'] to be set (e.g. 'M0000_2552').
    """
    users_result = await db.execute(
        select(User).join(Asset, Asset.user_id == User.id)
        .where(Asset.asset_type == "th_fund")
        .distinct()
    )
    users = list(users_result.scalars().all())
    if not users:
        logger.info("fetch_th_fund_prices: no users with th_fund assets")
        return {"inserted": 0, "funds": [], "skipped": []}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_rows: list[dict] = []
    all_fetched: list[str] = []
    all_skipped: list[str] = []

    async with httpx.AsyncClient(timeout=30) as client:
        for user in users:
            if not user.sec_api_key:
                logger.warning("fetch_th_fund_prices: user %s has no SEC API key — skipping", user.id)
                continue
            api_key = decrypt(user.sec_api_key)

            assets_result = await db.execute(
                select(Asset).where(Asset.asset_type == "th_fund", Asset.user_id == user.id)
            )
            assets = list(assets_result.scalars().all())

            rows, fetched, skipped = await _fetch_th_fund_for_user(client, assets, api_key, today)
            all_rows.extend(rows)
            all_fetched.extend(fetched)
            all_skipped.extend(skipped)

    inserted = await _upsert_prices(db, all_rows)
    logger.info("fetch_th_fund_prices: upserted %d rows for %d funds", inserted, len(all_fetched))
    return {"table": "prices", "inserted": inserted, "funds": all_fetched, "skipped": all_skipped}


# ---------------------------------------------------------------------------
# Historical prices (back-fill from earliest transaction)
# ---------------------------------------------------------------------------

_HISTORICAL_ASSET_TYPES = frozenset({"us_stock", "etf", "crypto", "gold"})


async def fetch_historical_prices(db: AsyncSession) -> dict:
    """Fetch full yfinance history for all priced assets, back to their earliest transaction."""
    assets_result = await db.execute(
        select(Asset).where(Asset.asset_type.in_(_HISTORICAL_ASSET_TYPES))
    )
    assets = list(assets_result.scalars().all())

    if not assets:
        logger.info("fetch_historical_prices: no priced assets found")
        return {"inserted": 0, "assets_processed": 0}

    total_inserted = 0
    processed = 0

    for asset in assets:
        earliest_result = await db.execute(
            select(func.min(Transaction.executed_at)).where(Transaction.asset_id == asset.id)
        )
        earliest_dt = earliest_result.scalar_one_or_none()
        if earliest_dt is None:
            logger.debug("fetch_historical_prices: no transactions for %s, skipping", asset.symbol)
            continue

        start_str = str(earliest_dt.date())

        def _fetch(symbol: str, start: str):
            ticker = yf.Ticker(symbol)
            return ticker.history(start=start, interval="1d")

        try:
            hist = await asyncio.get_event_loop().run_in_executor(None, _fetch, asset.symbol, start_str)
        except Exception as e:
            logger.warning("fetch_historical_prices: yfinance failed for %s: %s", asset.symbol, e)
            continue

        if hist.empty:
            logger.warning("fetch_historical_prices: empty history for %s from %s", asset.symbol, start_str)
            continue

        rows = []
        for ts, row in hist.iterrows():
            rows.append({
                "asset_id": asset.id,
                "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                "open": _to_decimal(row.get("Open")),
                "high": _to_decimal(row.get("High")),
                "low": _to_decimal(row.get("Low")),
                "close": _to_decimal(row.get("Close")),
                "volume": _to_decimal(row.get("Volume")),
            })

        if rows:
            inserted = await _upsert_prices(db, rows)
            total_inserted += inserted
            logger.info(
                "fetch_historical_prices: %s inserted=%d from=%s",
                asset.symbol, inserted, start_str,
            )

        processed += 1

    return {"inserted": total_inserted, "assets_processed": processed}
