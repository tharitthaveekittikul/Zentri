import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.top_down_analysis import TopDownAnalysis
from app.models.llm_call_log import LLMCallLog
from app.services.llm_service import get_llm_provider
from app.services.pipeline import create_log, finish_log, create_step, finish_step
from app.services.exchange_rate import get_current_usd_thb

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a professional financial analyst performing a top-down analysis.
Analyse the provided data and respond ONLY with valid JSON in this exact format:
{
  "mega_trend": "<industry trend and ATH pullback context, 2-3 sentences>",
  "financial_health": "<revenue and profit trend summary, 2-3 sentences>",
  "swot": {
    "strengths": ["<item>", "..."],
    "weaknesses": ["<item>", "..."],
    "opportunities": ["<item>", "..."],
    "threats": ["<item>", "..."]
  },
  "verdict": "BUY" | "SELL" | "HOLD",
  "target_price": <number or null>
}
Do not include any text outside the JSON object."""

FORMAT_REMINDER = 'Respond ONLY with the JSON object as specified. All four SWOT keys required. verdict must be BUY, SELL, or HOLD.'


def _parse_top_down(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        data = json.loads(text)
        if data.get("verdict") not in ("BUY", "SELL", "HOLD"):
            return None
        swot = data.get("swot", {})
        required_keys = {"strengths", "weaknesses", "opportunities", "threats"}
        if not required_keys.issubset(swot.keys()):
            return None
        return data
    except (json.JSONDecodeError, AttributeError):
        return None


async def job_run_top_down_analysis(ctx: dict, symbol: str, ath_drop_pct: float | None = None, user_id: str | None = None) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "run_top_down_analysis")
        current_step = None
        try:
            from app.models.asset import Asset
            from app.models.price import Price

            current_step = await create_step(db, log.id, "load_asset")
            a_result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
            asset = a_result.scalar_one_or_none()
            if not asset:
                raise ValueError(f"Asset {symbol} not found")

            since = datetime.now(timezone.utc) - timedelta(days=90)
            p_result = await db.execute(
                select(Price)
                .where(Price.asset_id == asset.id, Price.timestamp >= since)
                .order_by(desc(Price.timestamp))
                .limit(10)
            )
            prices = p_result.scalars().all()
            await finish_step(db, current_step, success=True, metadata={"symbol": symbol.upper()})

            current_step = await create_step(db, log.id, "fetch_news")
            from app.services.news_rag import list_recent_articles
            news_articles = await list_recent_articles(db, symbol=symbol, limit=10)
            news_context = "\n".join(
                f"- [{a.title}] {a.summary or ''}" for a in news_articles
            ) if news_articles else ""
            await finish_step(db, current_step, success=True, metadata={
                "news_articles": len(news_articles),
            })

            prices_txt = "\n".join(
                f"{p.timestamp.date()}: close={p.close}" for p in prices[:10]
            ) if prices else "No price history."

            ath_line = f"ATH pullback: -{ath_drop_pct:.1f}%\n" if ath_drop_pct else ""
            user_prompt = f"""Asset: {symbol}
{ath_line}
Recent price history (last 10 days):
{prices_txt}

Recent news:
{news_context}

Provide your top-down analysis as JSON."""

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            current_step = await create_step(db, log.id, "llm_call")
            llm = await get_llm_provider(db, "top_down_analysis")
            resp = await llm.complete(messages)
            parsed = _parse_top_down(resp.content)

            if parsed is None:
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": FORMAT_REMINDER})
                resp2 = await llm.complete(messages)
                parsed = _parse_top_down(resp2.content)
                if parsed is None:
                    raise ValueError(f"LLM returned malformed JSON after retry: {resp2.content[:200]}")
                resp = resp2

            await finish_step(db, current_step, success=True, metadata={
                "tokens_in": resp.tokens_in,
                "tokens_out": resp.tokens_out,
                "cost_usd": float(resp.cost_usd),
                "verdict": parsed["verdict"],
            })

            if user_id:
                try:
                    exchange_rate = await get_current_usd_thb(db)
                    cost_thb = float(resp.cost_usd) * float(exchange_rate) if exchange_rate else 0.0
                    db.add(LLMCallLog(
                        user_id=uuid.UUID(user_id),
                        feature_key="top_down_analysis",
                        provider=llm.provider_name,
                        model=getattr(llm, "model", "unknown"),
                        prompt_in=user_prompt,
                        response_out=resp.content,
                        tokens_in=resp.tokens_in,
                        tokens_out=resp.tokens_out,
                        cost_usd=resp.cost_usd,
                        cost_thb=cost_thb,
                        exchange_rate=exchange_rate or 0,
                    ))
                except Exception as log_err:
                    logger.warning("run_top_down_analysis: failed to save llm call log: %s", log_err)

            current_step = await create_step(db, log.id, "save_analysis")
            swot = parsed["swot"]
            analysis = TopDownAnalysis(
                asset_id=asset.id,
                job_id=str(log.id),
                mega_trend=parsed["mega_trend"],
                financial_health=parsed["financial_health"],
                ath_drop_pct=ath_drop_pct,
                swot_strengths=swot["strengths"],
                swot_weaknesses=swot["weaknesses"],
                swot_opportunities=swot["opportunities"],
                swot_threats=swot["threats"],
                verdict=parsed["verdict"],
                target_price=parsed.get("target_price"),
                provider=llm.provider_name,
                model=getattr(llm, "model", "unknown"),
                tokens_in=resp.tokens_in,
                tokens_out=resp.tokens_out,
                cost_usd=resp.cost_usd,
            )
            db.add(analysis)
            await db.commit()
            await finish_step(db, current_step, success=True, metadata={
                "verdict": parsed["verdict"],
                "analysis_id": str(analysis.id),
            })
            await finish_log(db, log, success=True)
            logger.info("run_top_down_analysis done symbol=%s verdict=%s", symbol, parsed["verdict"])
            return {"verdict": parsed["verdict"], "analysis_id": str(analysis.id)}

        except Exception as e:
            logger.exception("run_top_down_analysis failed symbol=%s: %s", symbol, e)
            if current_step is not None:
                await finish_step(db, current_step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
