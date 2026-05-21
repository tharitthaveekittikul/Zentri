from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt
from app.core.logging import get_logger
from app.models.feature_llm_config import FeatureLLMConfig
from app.models.provider_config import ProviderConfig
from app.services.exchange_rate import get_current_usd_thb
from app.services.llm_service import LLMResponse, calc_cost
from app.services.user_context import get_user_age_context
from sqlalchemy import select

logger = get_logger(__name__)

_IDENT_PLACEHOLDER = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)\}')


def _safe_format(template: str, vars_: dict) -> str:
    """Substitute only {simple_identifier} placeholders; leave JSON braces untouched."""
    return _IDENT_PLACEHOLDER.sub(
        lambda m: str(vars_[m.group(1)]) if m.group(1) in vars_ else m.group(0),
        template,
    )


@dataclass
class LLMGatewayResult:
    content: str
    prompt: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cost_thb: float
    exchange_rate: float
    model: str
    provider: str


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ToolLLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
    tokens_in: int
    tokens_out: int
    cost_usd: float
    stop_reason: str  # "end_turn", "tool_use"


FEATURE_KEYS = (
    "import_translator",
    "portfolio_analysis",
    "overview_analysis",
    "chat",
    "watchlist_scan",
    "watchlist_discovery",
    "ipo_analysis",
    "top_down_analysis",
    "top_down_discovery",
    "deep_dive",
    "peer_comparison",
    "bear_case",
    "combined_verdict",
)

FEATURES_WITH_AGE_CONTEXT: frozenset = frozenset({
    "portfolio_analysis", "chat", "watchlist_scan",
    "watchlist_discovery", "ipo_analysis", "overview_analysis",
})

FEATURES_AGE_IN_HUMAN_PROMPT: frozenset = frozenset({
    "portfolio_analysis", "overview_analysis",
})

DEFAULT_SYSTEM_PROMPTS: dict[str, str] = {
    "import_translator": (
        "You are a financial data normalization expert. Given a broker export file's structure "
        "and sample data, produce a JSON template that maps source fields to the canonical schema.\n\n"
        "CANONICAL FIELDS (use ONLY these as field_map values):\n"
        "trade_date, type, symbol, unit, price, currency, exchange, gross_amount, fee, "
        "gross_thb, fee_thb, exchange_rate, asset_type, platform, notes\n\n"
        "FIELD NOTES:\n"
        "- trade_date: output as dd/mm/yyyy (e.g. 26/04/2026). Convert any other format.\n"
        "- symbol: ALWAYS map the fund code / ticker / symbol source column to this. Never omit it.\n"
        "- type: ALWAYS map the source column that contains transaction type (Buy, Sell, Buy Note, etc.) "
        "  to 'type' in field_map. If you use value_transforms for 'type', the source column MUST also "
        "  appear in field_map (e.g. {\"Template\": \"type\"}). A value_transform without a field_map "
        "  entry has no effect.\n"
        "- price: cost per unit. Derive it via derived_fields (e.g. 'gross_amount / unit') if not explicit.\n"
        "- exchange: the stock exchange (e.g. SET, mai, NYSE, NASDAQ, FUND). Infer from context or set "
        "  a sensible default (Thai mutual funds → 'FUND', Thai stocks → 'SET', US stocks → 'NYSE').\n\n"
        "VALID type VALUES: BUY, SELL, DIVIDEND, REWARD, FEE, TRANSFER\n"
        "VALID asset_type VALUES: us_stock, thai_stock, th_fund, etf, crypto, gold, cash\n\n"
        "For nested JSON files, set json_path to the key path to the transaction array "
        "(e.g. \"transactions\"). For CSV or top-level arrays, set json_path to null.\n\n"
        "Return ONLY valid JSON — no explanation, no markdown:\n"
        "{\n"
        "  \"file_format\": \"csv\" or \"json\",\n"
        "  \"json_path\": null or \"transactions\",\n"
        "  \"field_map\": {\"source_col\": \"canonical_field\", ...},\n"
        "  \"value_transforms\": {\"type\": {\"Buy Note\": \"BUY\"}},\n"
        "  \"derived_fields\": {\"gross_thb\": \"unit * price * exchange_rate\"},\n"
        "  \"defaults\": {\"currency\": \"THB\", \"platform\": \"Broker Name\", \"exchange\": \"FUND\"},\n"
        "  \"asset_type_rules\": [{\"field\": \"exchange\", \"values\": [\"SET\"], \"asset_type\": \"thai_stock\"}],\n"
        "  \"asset_type_fallback\": \"thai_stock\"\n"
        "}"
    ),
    "portfolio_analysis": (
        "You are a portfolio analyst. Analyze the investor's portfolio allocation, performance, and risk. "
        "Provide concise, actionable insights with specific numbers. "
        "Use {primary_currency} as the base currency. Limit response to 3-5 key points, "
        "each as a short paragraph. Do not repeat data already shown."
    ),
    "overview_analysis": (
        "You are a portfolio health advisor. Assess the investor's overall portfolio and return a "
        "structured JSON health report. Use {primary_currency} as the base currency.\n\n"
        "Return ONLY valid JSON in this exact format — no text outside the object:\n"
        "{\"score\": <integer 0-100>, "
        "\"grade\": \"A\" | \"B\" | \"C\" | \"D\" | \"F\", "
        "\"health\": \"Excellent\" | \"Good\" | \"Moderate\" | \"Weak\" | \"Critical\", "
        "\"portfolio_adherence_pct\": <integer 0-100 or null if no target set>, "
        "\"insights\": [\"<insight>\", \"<insight>\", \"<insight>\"], "
        "\"top_action\": \"<single most important next action>\"}\n\n"
        "Insights: 2-4 items, each under 20 words. top_action: one actionable sentence."
    ),
    "chat": (
        "You are Zentri, a personal finance assistant. Help users understand their portfolio, "
        "investments, and financial markets. Use {primary_currency} as the base currency.\n\n"
        "SCOPE: Answer only finance-related questions — investments, stocks, funds, bonds, "
        "economics, and events that directly impact markets (e.g., interest rates, geopolitics, "
        "trade policy, political events affecting markets).\n\n"
        "OUT OF SCOPE: For unrelated questions (weather, sports trivia, cooking, etc.), respond "
        "ONLY with this JSON and nothing else:\n"
        "{\"type\": \"out_of_scope\", \"message\": \"I can only help with finance and investment "
        "questions. Try asking about your portfolio, a specific stock, or market trends.\"}\n\n"
        "Keep responses concise — 3-5 sentences unless depth is essential. "
        "Do not speculate on non-financial topics."
    ),
    "watchlist_scan": (
        "You are a financial analyst evaluating an asset as a potential buy opportunity. "
        "The user does not currently hold this asset. Analyze the recent price history and research context. "
        "Respond ONLY with valid JSON in this exact format — no text outside the object:\n"
        "{\"verdict\": \"BUY\" | \"HOLD\" | \"AVOID\", "
        "\"suggested_price\": <number or null>, "
        "\"reasoning\": \"<2-3 sentence explanation>\"}"
    ),
    "watchlist_discovery": (
        "You are a portfolio advisor. Based on the investor's current holdings, suggest assets worth watching. "
        "Respond ONLY with a valid JSON array — no text outside the array:\n"
        "[{\"symbol\": \"<TICKER>\", "
        "\"verdict\": \"BUY\" | \"HOLD\" | \"AVOID\", "
        "\"suggested_price\": <number or null>, "
        "\"reasoning\": \"<2-3 sentences>\"}]\n"
        "Suggest exactly 3 to 5 assets not already in the portfolio or watchlist."
    ),
    "ipo_analysis": (
        "You are a financial analyst specializing in IPO evaluations. "
        "Given IPO data, assess whether to Buy, Watch, or Skip this offering. "
        "Respond ONLY with valid JSON in this exact format — no text outside the object:\n"
        "{\"verdict\": \"BUY\" | \"WATCH\" | \"SKIP\", "
        "\"suggested_price\": <number or null>, "
        "\"reasoning\": \"<2-3 sentence explanation>\"}"
    ),
    "top_down_analysis": (
        "You are a professional financial analyst performing a top-down analysis.\n"
        "Analyse the provided data and respond ONLY with valid JSON in this exact format — no text outside the object:\n"
        "{\n"
        "  \"mega_trend\": \"<industry trend and ATH pullback context, 2-3 sentences>\",\n"
        "  \"financial_health\": \"<revenue and profit trend summary, 2-3 sentences>\",\n"
        "  \"swot\": {\n"
        "    \"strengths\": [\"<item>\"],\n"
        "    \"weaknesses\": [\"<item>\"],\n"
        "    \"opportunities\": [\"<item>\"],\n"
        "    \"threats\": [\"<item>\"]\n"
        "  },\n"
        "  \"verdict\": \"BUY\" | \"SELL\" | \"HOLD\",\n"
        "  \"target_price\": <number or null>\n"
        "}"
    ),
    "top_down_discovery": (
        "You are a market analyst identifying stocks pulling back from all-time highs. "
        "Given a list of candidate stocks with their ATH drop percentages and price history, "
        "identify the most promising ones for a full top-down analysis. "
        "Focus on mega trends, sector momentum, and the quality of the pullback."
    ),
    "deep_dive": (
        "You are a senior equity analyst specializing in business model assessment. "
        "You provide clear, structured company breakdowns focused on fundamentals and competitive positioning. "
        "Always respond with valid JSON matching the specified schema exactly. No markdown, no explanation outside JSON."
    ),
    "peer_comparison": (
        "You are a quantitative equity analyst specializing in relative valuation. "
        "You build precise peer comparison tables using financial data to identify the best value/growth opportunities. "
        "Always respond with valid JSON matching the specified schema exactly. No markdown, no explanation outside JSON."
    ),
    "bear_case": (
        "You are a skeptical short-seller conducting fundamental risk analysis. "
        "You identify the most serious structural and financial red flags, citing data where available. "
        "Always respond with valid JSON matching the specified schema exactly. No markdown, no explanation outside JSON."
    ),
    "combined_verdict": (
        "You are a chief investment officer synthesizing multiple research reports into a final investment verdict. "
        "You weigh evidence from all available analyses and provide a clear, actionable recommendation. "
        "Always respond with valid JSON matching the specified schema exactly. No markdown, no explanation outside JSON."
    ),
}

HUMAN_PROMPTS: dict[str, str] = {
    "import_translator": "File format: {file_format}\nHeaders/keys: {headers}\n\nSample rows (first 5):\n{sample_rows}",
    "portfolio_analysis": (
        "Holdings:\n{holdings_table}\n\n"
        "Cash:\n{cash_table}\n\n"
        "Performance: 1M {perf_1m}% | 3M {perf_3m}% | YTD {perf_ytd}%\n"
        "Total value: {total_value} {primary_currency}\n\n"
        "{age_context_line}"
        "Provide 3-5 key insights."
    ),
    "overview_analysis": (
        "Holdings:\n{holdings_table}\n\n"
        "Cash:\n{cash_table}\n\n"
        "Total value: {total_value} {primary_currency} | {num_holdings} holdings\n"
        "Unrealized P&L (all-time): {total_pnl_pct}%\n\n"
        "{age_context_line}"
        "Assess portfolio health and return the JSON report."
    ),
    "chat": "{message}",
    "watchlist_scan": (
        "Asset: {symbol}\n\n"
        "Recent price history (last 10 days):\n{prices_txt}\n\n"
        "Research context:\n{rag_context}\n\n"
        "Should I buy this asset? Provide your JSON verdict."
    ),
    "watchlist_discovery": (
        "Current portfolio holdings:\n{holdings_txt}\n\n"
        "Already on watchlist (exclude these):\n{watchlist_txt}\n\n"
        "Suggest 3-5 assets worth watching based on the portfolio above. Respond with JSON array."
    ),
    "ipo_analysis": (
        "Analyze this upcoming IPO and provide an investment recommendation.\n\n"
        "Symbol: {symbol}\n"
        "Company: {company_name}\n"
        "Sector: {sector}\n"
        "IPO Date: {ipo_date}\n"
        "Expected Price Range: {price_low} - {price_high} USD\n"
        "Business Description: {description}\n"
        "Market Cap: {market_cap}\n"
        "Trailing P/E: {pe_ratio}"
    ),
    "deep_dive": (
        "Analyze {company_name} ({symbol}) in the {sector} sector.\n\n"
        "Provide a 4-part deep dive:\n"
        "1. Business Model: How do they actually make money? Core product in plain English.\n"
        "2. Moat: Top 3 competitors. Does {symbol} have a durable edge "
        "(patent, switching_cost, network_effect, cost_structure) that rivals can't copy?\n"
        "3. Catalysts: Upcoming launches, earnings, regulatory events, or partnerships in the next 12 months.\n"
        "4. Asymmetry: Is there a low valuation floor vs high growth ceiling? Why or why not?\n\n"
        'Respond ONLY with this JSON:\n'
        '{{\n'
        '  "business_model": "...",\n'
        '  "moat": {{"edge_type": "patent|switching_cost|network_effect|cost_structure|none", '
        '"summary": "...", "competitors": ["T1", "T2", "T3"]}},\n'
        '  "catalysts": [{{"title": "...", "timeframe": "...", "impact": "high|medium|low"}}],\n'
        '  "asymmetry": {{"verdict": "yes|no|mixed", "floor": "...", "ceiling": "...", "reasoning": "..."}}\n'
        '}}'
    ),
    "peer_comparison": (
        "Analyze {symbol} ({sector}) relative to its peers using this financial data:\n\n"
        "{financial_table}\n\n"
        "Value/Growth Score = P/S TTM / YoY Revenue Growth %. Lower = better.\n"
        'Label: "BEST" for lowest score, "AVOID" for highest, "FAIR" for all others.\n\n'
        'Respond ONLY with this JSON:\n'
        '{{\n'
        '  "sector_label": "...",\n'
        '  "methodology_note": "Value/Growth Score = P/S TTM / YoY Revenue Growth %",\n'
        '  "ranked": [\n'
        '    {{"ticker": "...", "company_name": "...", "ps_ttm": 0.0, "ps_forward": 0.0,\n'
        '      "ev_ebitda": 0.0, "gross_margin_pct": 0.0, "yoy_revenue_growth_pct": 0.0,\n'
        '      "revenue_trend": "Reaccelerating|Accelerating|Stable|Decelerating|Declining",\n'
        '      "value_growth_score": 0.00, "label": "BEST|FAIR|AVOID", "notes": "..."}}\n'
        '  ]\n'
        '}}'
    ),
    "bear_case": (
        "Conduct a bear case analysis for {company_name} ({symbol}) in the {sector} sector.\n\n"
        "Financial data (yfinance):\n"
        "- Gross margins last 4 quarters: {gross_margins_4q}\n"
        "- YoY revenue growth: {revenue_growth_yoy}%\n"
        "- Operating margin: {operating_margin}%\n"
        "- Debt/Equity ratio: {debt_equity}\n"
        "- Short interest: {short_interest_pct}%\n\n"
        "Identify the 3 most serious red flags ranked by severity.\n"
        'Mark data_source "yfinance" if supported by data above, "llm_knowledge" otherwise.\n\n'
        'Respond ONLY with this JSON:\n'
        '{{\n'
        '  "red_flags": [\n'
        '    {{"rank": 1, "title": "...", "severity": "high|medium|low",\n'
        '      "data_source": "yfinance|llm_knowledge", "evidence": "...", "detail": "..."}}\n'
        '  ],\n'
        '  "summary": "..."\n'
        '}}'
    ),
    "combined_verdict": (
        "Synthesize the following research on {symbol} into a final verdict.\n"
        "Available analyses: {available_analyses}\n\n"
        "{top_down_summary}"
        "{deep_dive_summary}"
        "{peer_comparison_summary}"
        "{bear_case_summary}"
        "\nProvide a final investment verdict with actionable price targets.\n"
        "For entry_price: recommend a specific buy zone based on current valuation and pullback context.\n"
        "For target_price: 12-month price target based on fundamentals and peer multiples.\n"
        "For stop_loss: price where the thesis is invalidated (support level or % below entry).\n"
        "For risk_reward: (target_price - entry_price) / (entry_price - stop_loss). Use null if price data is insufficient.\n\n"
        'Respond ONLY with this JSON:\n'
        '{{\n'
        '  "verdict": "strong_buy|buy|hold|sell|strong_sell",\n'
        '  "conviction": 7,\n'
        '  "bull_thesis": "...",\n'
        '  "bear_thesis": "...",\n'
        '  "key_risks": ["...", "..."],\n'
        '  "reasoning": "...",\n'
        '  "based_on": ["top_down_analysis", "deep_dive"],\n'
        '  "entry_price": 580.00,\n'
        '  "target_price": 700.00,\n'
        '  "stop_loss": 520.00,\n'
        '  "risk_reward": 2.0\n'
        '}}'
    ),
}


class LLMAdapter(ABC):
    @abstractmethod
    async def complete(self, system: str, human: str, model: str) -> LLMResponse: ...

    @abstractmethod
    async def fetch_models(self) -> list[str]: ...

    @abstractmethod
    async def complete_with_tools(
        self,
        system: str,
        messages: list[dict],
        model: str,
        tools: list[dict],
    ) -> ToolLLMResponse:
        """Send a multi-turn conversation with tool definitions.
        messages uses OpenAI neutral format (role/content/tool_calls/tool_call_id).
        tools uses neutral format: [{name, description, parameters (JSON schema)}].
        """
        ...


class AnthropicAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        from app.services.llm_service import LLMQuotaExceededError
        try:
            msg = await self._client.messages.create(
                model=model, max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": human}],
            )
        except Exception as exc:
            try:
                import anthropic
                if isinstance(exc, anthropic.RateLimitError):
                    raise LLMQuotaExceededError("anthropic", "https://console.anthropic.com/settings/billing") from exc
            except ImportError:
                pass
            raise
        tokens_in = msg.usage.input_tokens
        tokens_out = msg.usage.output_tokens
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=msg.content[0].text, tokens_in=tokens_in,
                           tokens_out=tokens_out, cost_usd=cost_usd)

    async def fetch_models(self) -> list[str]:
        result = await self._client.models.list()
        return [m.id for m in result.data]

    async def complete_with_tools(
        self, system: str, messages: list[dict], model: str, tools: list[dict]
    ) -> ToolLLMResponse:
        import json as _json
        anthropic_tools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in tools
        ]
        anthropic_messages = _to_anthropic_messages(messages)
        msg = await self._client.messages.create(
            model=model, max_tokens=2048, system=system,
            messages=anthropic_messages, tools=anthropic_tools,
        )
        tokens_in = msg.usage.input_tokens
        tokens_out = msg.usage.output_tokens
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        text_content = next(
            (b.text for b in msg.content if hasattr(b, "text")), None
        )
        tool_calls = [
            ToolCall(id=b.id, name=b.name, arguments=dict(b.input))
            for b in msg.content if hasattr(b, "type") and b.type == "tool_use"
        ]
        return ToolLLMResponse(
            content=text_content, tool_calls=tool_calls,
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=float(cost_usd),
            stop_reason="tool_use" if tool_calls else "end_turn",
        )


class OpenAIAdapter(LLMAdapter):
    def __init__(self, api_key: str, base_url: str | None = None):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        from app.services.llm_service import LLMQuotaExceededError
        try:
            resp = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": human}],
            )
        except Exception as exc:
            try:
                import openai
                if isinstance(exc, openai.RateLimitError):
                    raise LLMQuotaExceededError("openai", "https://platform.openai.com/settings/organization/billing") from exc
            except ImportError:
                pass
            raise
        tokens_in = resp.usage.prompt_tokens
        tokens_out = resp.usage.completion_tokens
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=resp.choices[0].message.content or "",
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd)

    async def fetch_models(self) -> list[str]:
        models = await self._client.models.list()
        return [m.id for m in models.data if m.id.startswith(("gpt-", "o1", "o3"))]

    async def complete_with_tools(
        self, system: str, messages: list[dict], model: str, tools: list[dict]
    ) -> ToolLLMResponse:
        import json as _json
        oai_tools = [
            {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
            for t in tools
        ]
        all_messages = [{"role": "system", "content": system}] + messages
        resp = await self._client.chat.completions.create(
            model=model, messages=all_messages, tools=oai_tools,
        )
        choice = resp.choices[0]
        tokens_in = resp.usage.prompt_tokens if resp.usage else 0
        tokens_out = resp.usage.completion_tokens if resp.usage else 0
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                args = _json.loads(tc.function.arguments or "{}")
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        return ToolLLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=float(cost_usd),
            stop_reason="tool_use" if tool_calls else "end_turn",
        )


class GeminiAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._genai = genai

    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        import asyncio
        from app.services.llm_service import LLMQuotaExceededError
        m = self._genai.GenerativeModel(model_name=model, system_instruction=system)
        try:
            response = await asyncio.to_thread(m.generate_content, human)
        except Exception as exc:
            try:
                from google.api_core.exceptions import ResourceExhausted
                if isinstance(exc, ResourceExhausted):
                    raise LLMQuotaExceededError("gemini", "https://aistudio.google.com/billing") from exc
            except ImportError:
                pass
            raise
        tokens_in = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        tokens_out = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=response.text, tokens_in=tokens_in,
                           tokens_out=tokens_out, cost_usd=cost_usd)

    async def fetch_models(self) -> list[str]:
        import asyncio
        models = await asyncio.to_thread(self._genai.list_models)
        return [
            m.name.replace("models/", "")
            for m in models
            if "generateContent" in (m.supported_generation_methods or [])
        ]

    async def complete_with_tools(
        self, system: str, messages: list[dict], model: str, tools: list[dict]
    ) -> ToolLLMResponse:
        import asyncio
        gemini_tools = [{
            "function_declarations": [
                {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
                for t in tools
            ]
        }]
        m = self._genai.GenerativeModel(
            model_name=model,
            system_instruction=system,
            tools=gemini_tools,
        )
        import json as _json

        def _func_name_for_tool_call(msgs, tool_call_id, up_to):
            for prev in reversed(msgs[:up_to]):
                for tc in (prev.get("tool_calls") or []):
                    if tc.get("id") == tool_call_id:
                        return tc.get("function", {}).get("name") or tc.get("name", "unknown")
            return "unknown"

        history = []
        for i, msg in enumerate(messages[:-1]):
            msg_role = msg["role"]
            if msg_role == "assistant":
                parts = []
                if msg.get("content"):
                    parts.append({"text": msg["content"]})
                for tc in (msg.get("tool_calls") or []):
                    func = tc.get("function", {})
                    name = func.get("name") or tc.get("name", "")
                    args_raw = func.get("arguments") or tc.get("arguments") or "{}"
                    args = _json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
                    parts.append({"function_call": {"name": name, "args": args}})
                history.append({"role": "model", "parts": parts if parts else [{"text": ""}]})
            elif msg_role == "tool":
                fname = _func_name_for_tool_call(messages, msg.get("tool_call_id", ""), i)
                history.append({"role": "user", "parts": [
                    {"function_response": {"name": fname, "response": {"result": msg.get("content", "")}}}
                ]})
            else:
                history.append({"role": "user", "parts": [{"text": msg.get("content") or ""}]})

        last_msg = messages[-1] if messages else {}
        if last_msg.get("role") == "tool":
            fname = _func_name_for_tool_call(messages, last_msg.get("tool_call_id", ""), len(messages) - 1)
            last_content = [{"function_response": {"name": fname, "response": {"result": last_msg.get("content", "")}}}]
        else:
            last_content = last_msg.get("content") or ""

        chat_session = m.start_chat(history=history)
        response = await asyncio.to_thread(chat_session.send_message, last_content)
        tool_calls = []
        content_text = None
        for part in response.parts:
            if hasattr(part, "function_call") and part.function_call.name:
                fc = part.function_call
                tool_calls.append(ToolCall(
                    id=f"gemini_{fc.name}_{uuid.uuid4().hex[:8]}",
                    name=fc.name,
                    arguments=dict(fc.args),
                ))
            elif hasattr(part, "text") and part.text:
                content_text = part.text
        usage = response.usage_metadata
        tokens_in = usage.prompt_token_count if usage else 0
        tokens_out = usage.candidates_token_count if usage else 0
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        logger.info("Gemini tool call: model=%s tools_called=%d tokens=%d/%d", model, len(tool_calls), tokens_in, tokens_out)
        return ToolLLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            stop_reason="tool_use" if tool_calls else "end_turn",
        )


class OllamaAdapter(LLMAdapter):
    def __init__(self, host_url: str):
        self._host = host_url.rstrip("/")

    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.post(f"{self._host}/api/chat", json={
                "model": model, "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": human},
                ],
            })
            resp.raise_for_status()
            data = resp.json()
        tokens_in = data.get("prompt_eval_count", 0)
        tokens_out = data.get("eval_count", 0)
        return LLMResponse(content=data["message"]["content"],
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=0.0)

    async def fetch_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(f"{self._host}/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]

    async def complete_with_tools(
        self, system: str, messages: list[dict], model: str, tools: list[dict]
    ) -> ToolLLMResponse:
        import json as _json
        oai_tools = [
            {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
            for t in tools
        ]
        all_messages = [{"role": "system", "content": system}] + messages
        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.post(f"{self._host}/v1/chat/completions", json={
                "model": model, "messages": all_messages, "tools": oai_tools,
            })
            resp.raise_for_status()
            data = resp.json()
        choice = data["choices"][0]
        message = choice["message"]
        usage = data.get("usage", {})
        tool_calls = []
        for tc in message.get("tool_calls") or []:
            args = _json.loads(tc["function"].get("arguments", "{}"))
            tool_calls.append(ToolCall(id=tc["id"], name=tc["function"]["name"], arguments=args))
        return ToolLLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            cost_usd=0.0,
            stop_reason="tool_use" if tool_calls else "end_turn",
        )


class OpenRouterAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": human}],
        )
        usage = resp.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=resp.choices[0].message.content or "",
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd)

    async def fetch_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            return [m["id"] for m in resp.json().get("data", [])]

    async def complete_with_tools(
        self, system: str, messages: list[dict], model: str, tools: list[dict]
    ) -> ToolLLMResponse:
        import json as _json
        oai_tools = [
            {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
            for t in tools
        ]
        all_messages = [{"role": "system", "content": system}] + messages
        resp = await self._client.chat.completions.create(
            model=model, messages=all_messages, tools=oai_tools,
        )
        choice = resp.choices[0]
        usage = resp.usage
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                args = _json.loads(tc.function.arguments or "{}")
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        return ToolLLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            cost_usd=float(calc_cost(model, usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0)),
            stop_reason="tool_use" if tool_calls else "end_turn",
        )


def _to_anthropic_messages(messages: list[dict]) -> list[dict]:
    """Convert neutral (OpenAI-style) messages to Anthropic format."""
    import json as _json
    result = []
    for m in messages:
        role = m.get("role")
        if role == "tool":
            content = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m.get("content", "")}
            if result and result[-1]["role"] == "user" and isinstance(result[-1]["content"], list):
                result[-1]["content"].append(content)
            else:
                result.append({"role": "user", "content": [content]})
        elif role == "assistant":
            blocks: list = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls") or []:
                func = tc.get("function", {})
                name = func.get("name", tc.get("name", ""))
                args_raw = func.get("arguments", tc.get("arguments", "{}"))
                args = _json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
                blocks.append({"type": "tool_use", "id": tc["id"], "name": name, "input": args})
            result.append({"role": "assistant", "content": blocks if blocks else ""})
        else:
            result.append({"role": role, "content": m.get("content", "")})
    return result


def _build_adapter(provider: str, api_key: str | None, host_url: str | None) -> LLMAdapter:
    if provider == "anthropic":
        return AnthropicAdapter(api_key or "")
    if provider == "openai":
        return OpenAIAdapter(api_key or "")
    if provider == "gemini":
        return GeminiAdapter(api_key or "")
    if provider == "ollama":
        return OllamaAdapter(host_url or "http://localhost:11434")
    if provider == "openrouter":
        return OpenRouterAdapter(api_key or "")
    raise ValueError(f"Unknown provider: {provider}")


class LLMGateway:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def complete(self, feature_key: str, user_id: uuid.UUID, variables: dict) -> LLMGatewayResult:
        from app.models.llm_call_log import LLMCallLog

        config = await self._get_feature_config(feature_key, user_id)
        provider = await self._get_provider(config.provider_config_id)
        api_key = decrypt(provider.encrypted_api_key) if provider.encrypted_api_key else None
        adapter = _build_adapter(provider.provider, api_key, provider.host_url)

        from app.models.user import User
        user_row = (await self._db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

        vars_ = dict(variables)
        vars_["current_date"] = datetime.now().strftime("%A, %Y-%m-%d")
        vars_["primary_currency"] = (getattr(user_row, "currency_primary", None) or "USD") if user_row else "USD"
        vars_.setdefault("age_context_line", "")

        age_prefix = ""
        if feature_key in FEATURES_WITH_AGE_CONTEXT and user_row:
            age_ctx = get_user_age_context(user_row)
            if age_ctx:
                if feature_key in FEATURES_AGE_IN_HUMAN_PROMPT:
                    vars_["age_context_line"] = (
                        f"Investor context: age {age_ctx['current_age']}, "
                        f"planning until age {age_ctx['plan_to_age']} "
                        f"({age_ctx['years_remaining']} years remaining).\n\n"
                    )
                else:
                    age_prefix = f"{age_ctx['prompt']}\n\n"
        logger.debug("Age context: %s for feature=%s", "injected" if (age_prefix or vars_["age_context_line"]) else "none", feature_key)

        system_template = config.system_prompt or DEFAULT_SYSTEM_PROMPTS.get(feature_key, "")
        human_template = HUMAN_PROMPTS[feature_key]
        current_date_prefix = f"Current date: {vars_['current_date']}\n\n"
        system = current_date_prefix + age_prefix + _safe_format(system_template, vars_)
        human = _safe_format(human_template, vars_)
        logger.info("LLM call: feature=%s provider=%s model=%s", feature_key, provider.provider, config.model)

        response: LLMResponse = await adapter.complete(system, human, config.model)

        usd_thb = await get_current_usd_thb(self._db)
        cost_thb = float(response.cost_usd) * float(usd_thb) if usd_thb else 0.0

        log = LLMCallLog(
            user_id=user_id,
            feature_key=feature_key,
            provider=provider.provider,
            model=config.model,
            prompt_in=f"SYSTEM: {system}\n\nHUMAN: {human}",
            response_out=response.content,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=response.cost_usd,
            cost_thb=cost_thb,
            exchange_rate=float(usd_thb) if usd_thb else 0.0,
        )
        self._db.add(log)
        await self._db.flush()

        logger.info("LLM logged: tokens_in=%d tokens_out=%d cost_usd=%.6f",
                    response.tokens_in, response.tokens_out, response.cost_usd)
        return LLMGatewayResult(
            content=response.content,
            prompt=human,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=float(response.cost_usd),
            cost_thb=cost_thb,
            exchange_rate=float(usd_thb) if usd_thb else 0.0,
            model=config.model,
            provider=provider.provider,
        )

    async def complete_chat(
        self, user_id: uuid.UUID, messages: list[dict]
    ) -> LLMGatewayResult:
        import json as _json
        from app.models.llm_call_log import LLMCallLog
        from app.services.chat_tools import TOOL_DEFINITIONS, execute_tool

        config = await self._get_feature_config("chat", user_id)
        provider = await self._get_provider(config.provider_config_id)
        api_key = decrypt(provider.encrypted_api_key) if provider.encrypted_api_key else None
        adapter = _build_adapter(provider.provider, api_key, provider.host_url)

        from app.models.user import User
        user_row = (await self._db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        currency = (getattr(user_row, "currency_primary", None) or "USD") if user_row else "USD"

        vars_: dict = {"current_date": datetime.now().strftime("%A, %Y-%m-%d"), "primary_currency": currency}
        age_prefix = ""
        if user_row:
            age_ctx = get_user_age_context(user_row)
            if age_ctx:
                age_prefix = f"{age_ctx['prompt']}\n\n"

        system_template = config.system_prompt or DEFAULT_SYSTEM_PROMPTS.get("chat", "")
        system = f"Current date: {vars_['current_date']}\n\n" + age_prefix + _safe_format(system_template, vars_)

        chat_messages = list(messages)
        total_tokens_in = 0
        total_tokens_out = 0
        total_cost_usd = 0.0
        final_content = ""
        MAX_TOOL_ROUNDS = 5

        for _ in range(MAX_TOOL_ROUNDS):
            resp = await adapter.complete_with_tools(system, chat_messages, config.model, TOOL_DEFINITIONS)
            total_tokens_in += resp.tokens_in
            total_tokens_out += resp.tokens_out
            total_cost_usd += resp.cost_usd

            if resp.stop_reason == "end_turn" or not resp.tool_calls:
                final_content = resp.content or ""
                break

            chat_messages.append({
                "role": "assistant",
                "content": resp.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.name, "arguments": _json.dumps(tc.arguments)}}
                    for tc in resp.tool_calls
                ],
            })
            for tc in resp.tool_calls:
                logger.info("Chat tool call: %s args=%s", tc.name, tc.arguments)
                tool_result = await execute_tool(tc.name, tc.arguments, self._db, user_id, currency)
                chat_messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_result})
        else:
            final_content = resp.content or "I ran into a loop — please rephrase your question."

        usd_thb = await get_current_usd_thb(self._db)
        cost_thb = total_cost_usd * float(usd_thb) if usd_thb else 0.0

        log = LLMCallLog(
            user_id=user_id, feature_key="chat",
            provider=provider.provider, model=config.model,
            prompt_in=_json.dumps(messages[-1]) if messages else "",
            response_out=final_content,
            tokens_in=total_tokens_in, tokens_out=total_tokens_out,
            cost_usd=total_cost_usd, cost_thb=cost_thb,
            exchange_rate=float(usd_thb) if usd_thb else 0.0,
        )
        self._db.add(log)
        await self._db.flush()

        logger.info("Chat complete: tokens_in=%d tokens_out=%d cost_usd=%.6f tool_rounds=%d",
                    total_tokens_in, total_tokens_out, total_cost_usd, len(chat_messages))
        return LLMGatewayResult(
            content=final_content, prompt="",
            tokens_in=total_tokens_in, tokens_out=total_tokens_out,
            cost_usd=total_cost_usd, cost_thb=cost_thb,
            exchange_rate=float(usd_thb) if usd_thb else 0.0,
            model=config.model, provider=provider.provider,
        )

    async def _get_feature_config(self, feature_key: str, user_id: uuid.UUID) -> FeatureLLMConfig:
        result = await self._db.execute(
            select(FeatureLLMConfig).where(
                FeatureLLMConfig.feature_key == feature_key,
                FeatureLLMConfig.user_id == user_id,
            )
        )
        config = result.scalar_one_or_none()
        if not config:
            raise ValueError(f"No LLM config for feature '{feature_key}'. Configure it in Settings → AI.")
        return config

    async def _get_provider(self, provider_config_id: uuid.UUID) -> ProviderConfig:
        result = await self._db.execute(
            select(ProviderConfig).where(ProviderConfig.id == provider_config_id)
        )
        provider = result.scalar_one_or_none()
        if not provider:
            raise ValueError("Provider config not found")
        if not provider.is_connected:
            raise ValueError(f"Provider '{provider.provider}' is not connected. Test connection in Settings → AI.")
        return provider
