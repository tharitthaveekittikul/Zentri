"use client";

import { ChatMessageWithMeta } from "@/lib/services/chat";

const STATIC_CHIPS: { label: string; prompt: string; tool: string }[] = [
  { label: "My portfolio", prompt: "Show my portfolio summary", tool: "get_portfolio_summary" },
  { label: "My holdings", prompt: "Show my holdings", tool: "get_holdings" },
  { label: "My watchlist", prompt: "Show my watchlist", tool: "get_watchlist" },
  { label: "My cash", prompt: "How much cash do I have?", tool: "get_portfolio_summary" },
  { label: "Search news", prompt: "Search latest market news", tool: "search_news" },
];

const TICKER_NOISE = new Set([
  "I", "USD", "THB", "ETF", "IPO", "ATH", "YTD", "OK", "AI", "PL",
  "AND", "OR", "THE", "FOR", "NOT", "ARE", "HAS", "WAS",
]);
const TICKER_RE = /\b([A-Z]{2,5})\b/g;

function extractLatestTicker(messages: ChatMessageWithMeta[]): string | null {
  const last5 = messages.slice(-5);
  for (let i = last5.length - 1; i >= 0; i--) {
    const text = last5[i].content ?? "";
    const matches = [...text.matchAll(TICKER_RE)].map((m) => m[1]);
    const tickers = matches.filter((t) => !TICKER_NOISE.has(t));
    if (tickers.length > 0) return tickers[tickers.length - 1];
  }
  return null;
}

interface ChatQuickActionsProps {
  messages: ChatMessageWithMeta[];
  onSelect: (text: string) => void;
}

export function ChatQuickActions({ messages, onSelect }: ChatQuickActionsProps) {
  const ticker = extractLatestTicker(messages);

  return (
    <div className="flex gap-2 overflow-x-auto py-2 px-1 shrink-0">
      {STATIC_CHIPS.map((chip) => (
        <button
          key={chip.label}
          onClick={() => onSelect(chip.prompt)}
          className="flex flex-col items-start border border-border rounded-lg px-3 py-1.5 text-xs whitespace-nowrap text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
        >
          <span>{chip.label}</span>
          <span className="text-[10px] text-muted-foreground/50 font-mono">{chip.tool}</span>
        </button>
      ))}
      {ticker && (
        <button
          onClick={() => onSelect(`Analyze ${ticker}`)}
          className="flex flex-col items-start border border-primary/20 rounded-lg px-3 py-1.5 text-xs whitespace-nowrap bg-primary/10 text-primary hover:bg-primary/20 shrink-0 transition-colors"
        >
          <span>Analyze {ticker}</span>
          <span className="text-[10px] text-primary/50 font-mono">get_symbol_analysis</span>
        </button>
      )}
    </div>
  );
}
