import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.llm_conversation import LLMConversation
from app.services.llm_service import get_llm_provider
from app.services.pipeline import create_log, finish_log
from app.services.rag_service import get_or_create_collection, search

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a professional financial analyst. Analyse the provided portfolio position and market data.
Respond ONLY with valid JSON in this exact format:
{"verdict": "BUY" | "SELL" | "HOLD", "target_price": <number or null>, "reasoning": "<2-3 sentence explanation>"}
Do not include any text outside the JSON object."""

FORMAT_REMINDER = 'Your previous response was not valid JSON. Respond ONLY with the JSON object: {"verdict": "BUY"|"SELL"|"HOLD", "target_price": <number or null>, "reasoning": "<explanation>"}'


async def job_run_analysis(ctx: dict, symbol: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "run_analysis")
        try:
            from app.models.asset import Asset
            from app.models.holding import Holding
            from app.models.price import Price

            a_result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
            asset = a_result.scalar_one_or_none()
            if not asset:
                raise ValueError(f"Asset {symbol} not found")

            h_result = await db.execute(select(Holding).where(Holding.asset_id == asset.id))
            holdings = h_result.scalars().all()

            since = datetime.now(timezone.utc) - timedelta(days=90)
            p_result = await db.execute(
                select(Price)
                .where(Price.asset_id == asset.id, Price.timestamp >= since)
                .order_by(desc(Price.timestamp))
                .limit(90)
            )
            prices = p_result.scalars().all()

            collection = get_or_create_collection(symbol)
            rag_chunks = search(collection, query=f"{symbol} financial analysis earnings revenue")
            rag_context = "\n\n---\n\n".join(rag_chunks) if rag_chunks else "No documents available."

            holdings_txt = "\n".join(
                f"- {h.quantity} units @ avg cost {h.avg_cost}" for h in holdings
            ) or "No current holdings."
            prices_txt = "\n".join(
                f"{p.timestamp.date()}: close={p.close}" for p in prices[:10]
            ) if prices else "No price history."

            user_prompt = f"""Asset: {symbol}

Holdings:
{holdings_txt}

Recent price history (last 10 days):
{prices_txt}

Research documents context:
{rag_context}

Provide your BUY/SELL/HOLD verdict as JSON."""

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            llm = await get_llm_provider(db)
            resp = await llm.complete(messages)
            parsed = _parse_verdict(resp.content)

            if parsed is None:
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": FORMAT_REMINDER})
                resp2 = await llm.complete(messages)
                parsed = _parse_verdict(resp2.content)
                if parsed is None:
                    raise ValueError(f"LLM returned malformed JSON after retry: {resp2.content[:200]}")
                resp = resp2

            analysis = AIAnalysis(
                asset_id=asset.id,
                job_id=str(log.id),
                verdict=parsed["verdict"],
                target_price=parsed.get("target_price"),
                reasoning=parsed["reasoning"],
                provider=type(llm).__name__.replace("Provider", "").lower(),
                model=getattr(llm, "model", "unknown"),
                tokens_in=resp.tokens_in,
                tokens_out=resp.tokens_out,
                cost_usd=resp.cost_usd,
            )
            db.add(analysis)
            await db.flush()

            for i, msg in enumerate(messages + [{"role": "assistant", "content": resp.content}]):
                db.add(LLMConversation(
                    analysis_id=analysis.id,
                    role=msg["role"],
                    content=msg["content"],
                    message_order=i,
                ))

            await db.commit()
            await finish_log(db, log, success=True)
            logger.info("run_analysis done symbol=%s verdict=%s", symbol, parsed["verdict"])
            return {"verdict": parsed["verdict"], "analysis_id": str(analysis.id)}
        except Exception as e:
            logger.exception("run_analysis failed symbol=%s: %s", symbol, e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise


def _parse_verdict(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        data = json.loads(text)
        if data.get("verdict") not in ("BUY", "SELL", "HOLD"):
            return None
        return data
    except (json.JSONDecodeError, AttributeError):
        return None
