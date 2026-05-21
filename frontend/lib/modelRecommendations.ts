export type ModelAlternative = {
  model: string;
  note: string;
};

export type ModelRecommendation = {
  recommended: string;
  why: string;
  alternatives: ModelAlternative[];
  cost_tier: "low" | "medium" | "high";
};

export const MODEL_RECOMMENDATIONS: Record<string, ModelRecommendation> = {
  import_translator: {
    recommended: "gemini-2.5-flash-lite",
    why: "Market leader for cost-efficient structured extraction. At $0.10/$0.40, it undercuts Haiku while maintaining high reliability for JSON schemas.",
    alternatives: [
      {
        model: "gpt-4o-mini",
        note: "Strong alternative for legacy CSV parsing",
      },
      {
        model: "claude-haiku-4-5-20251001",
        note: "Faster TTFT, but 10x the cost of Flash-Lite",
      },
    ],
    cost_tier: "low",
  },
  portfolio_analysis: {
    recommended: "claude-sonnet-4-6",
    why: "The 'Goldilocks' model for finance. Better nuancing on risk-adjusted returns than GPT-4o.",
    alternatives: [
      {
        model: "gemini-3-pro",
        note: "Superior for massive portfolios due to context window",
      },
      {
        model: "gpt-5",
        note: "Use only for institutional-grade deep dive reports",
      },
    ],
    cost_tier: "medium",
  },
  chat: {
    recommended: "gemini-2.5-flash",
    why: "Best balance of native speed and conversational personality. Extremely low latency for UI responsiveness.",
    alternatives: [
      {
        model: "claude-haiku-4-5-20251001",
        note: "Very concise; great for technical Q&A",
      },
      {
        model: "o3-mini",
        note: "Best for 'Help me fix this code' chat interactions",
      },
    ],
    cost_tier: "low",
  },
  watchlist_scan: {
    recommended: "gemini-2.5-flash-lite",
    why: "Purely a cost play. Scanning 100+ assets in batch is nearly free at this tier.",
    alternatives: [
      {
        model: "gpt-4o-mini",
        note: "Industry standard for simple classification",
      },
    ],
    cost_tier: "low",
  },
  ipo_analysis: {
    recommended: "gpt-5",
    why: "Frontier reasoning is required to synthesize complex S-1 filings and market sentiment accurately.",
    alternatives: [
      {
        model: "claude-opus-4-7",
        note: "Best for qualitative risk assessment",
      },
      {
        model: "gemini-3-pro",
        note: "Strong for sector-wide comparative analysis",
      },
    ],
    cost_tier: "high",
  },
  overview_analysis: {
    recommended: "claude-sonnet-4-6",
    why: "Market leader for reliability in complex JSON synthesis. It maintains higher reasoning consistency for weighted scoring across multiple assets compared to Flash-tier models.",
    alternatives: [
      {
        model: "gemini-3.1-pro",
        note: "Best for ultra-large portfolios thanks to its 10M+ context window and deep research capabilities",
      },
      {
        model: "gpt-5.4",
        note: "Strong reasoning for outlier detection, but slightly higher latency for real-time dashboards",
      },
      {
        model: "gemini-3.1-flash-lite",
        note: "Extreme budget option ($0.10/$0.40) for simple high-volume summaries",
      },
    ],
    cost_tier: "medium",
  },
  top_down_analysis: {
    recommended: "claude-sonnet-4-6",
    why: "Top-down analysis requires multi-step reasoning: synthesizing SEC filings, earnings trends, and macro context into a structured SWOT. Sonnet delivers the best balance of reasoning depth and JSON reliability for this complexity.",
    alternatives: [
      {
        model: "claude-opus-4-7",
        note: "Best qualitative SWOT depth — use when accuracy matters more than cost",
      },
      {
        model: "gpt-5",
        note: "Strong on financial document synthesis from SEC filings",
      },
      {
        model: "gemini-2.5-flash",
        note: "Budget option — fast and cheap, but SWOT quality is shallower",
      },
    ],
    cost_tier: "medium",
  },
  top_down_discovery: {
    recommended: "gemini-2.5-flash-lite",
    why: "Discovery is a screening task, not a reasoning task — it scans price data for ATH pullbacks and queues candidates. A fast, cheap model is ideal here since the real analysis happens in top_down_analysis.",
    alternatives: [
      {
        model: "claude-haiku-4-5-20251001",
        note: "Slightly higher quality filtering with minimal cost increase",
      },
      {
        model: "gpt-4o-mini",
        note: "Good alternative if you prefer OpenAI for screening tasks",
      },
    ],
    cost_tier: "low",
  },
  deep_dive: {
    recommended: "claude-sonnet-4-6",
    why: "Deep Dive requires structured multi-section reasoning (business model, moat, catalysts, asymmetry) from LLM knowledge alone — no data injection. Sonnet delivers narrative depth and JSON reliability at a sensible cost.",
    alternatives: [
      {
        model: "claude-opus-4-7",
        note: "Best narrative quality for flagship companies (AAPL, NVDA, TSLA)",
      },
      {
        model: "gemini-2.5-flash",
        note: "Budget option — adequate for well-known large caps",
      },
    ],
    cost_tier: "medium",
  },
  peer_comparison: {
    recommended: "claude-sonnet-4-6",
    why: "Runs 2 LLM calls per analysis — peer discovery then financial table scoring. Sonnet handles live P/S, EV/EBITDA, and YoY growth tables reliably without frontier cost.",
    alternatives: [
      {
        model: "gpt-4o",
        note: "Strong alternative for financial table interpretation",
      },
      {
        model: "gemini-2.5-flash-lite",
        note: "Cost-optimized — peer discovery sub-call is lightweight",
      },
    ],
    cost_tier: "medium",
  },
  bear_case: {
    recommended: "claude-sonnet-4-6",
    why: "Interprets injected yfinance metrics (margins, short interest, debt/equity) combined with LLM structural risk knowledge. Sonnet ranks severity nuances well without needing a frontier model.",
    alternatives: [
      {
        model: "gpt-4o",
        note: "Equally strong at structured risk assessment",
      },
      {
        model: "claude-haiku-4-5-20251001",
        note: "Fine for large-cap stocks with obvious risk profiles",
      },
    ],
    cost_tier: "medium",
  },
  combined_verdict: {
    recommended: "claude-sonnet-4-6",
    why: "Synthesizes up to 4 analyses (Top-Down, Deep Dive, Peer Comparison, Bear Case) into one conviction score — the highest-reasoning task in the pipeline. Sonnet holds multi-document context well; upgrade to Opus for high-stakes position sizing.",
    alternatives: [
      {
        model: "claude-opus-4-7",
        note: "Best synthesis quality — recommended when verdict drives real capital allocation",
      },
      {
        model: "gpt-5",
        note: "Superior multi-document reasoning if you prefer OpenAI",
      },
    ],
    cost_tier: "medium",
  },
};

export const COST_TIER_LABELS: Record<string, string> = {
  low: "Low cost",
  medium: "Medium cost",
  high: "High cost",
};
