export interface PageEntry {
  label: string;
  url: string;
  keywords: string[];
}

export const PAGES: PageEntry[] = [
  { label: "Overview", url: "/overview", keywords: ["dashboard", "summary"] },
  { label: "Portfolio", url: "/portfolio", keywords: ["holdings", "assets"] },
  { label: "Transactions", url: "/transactions", keywords: ["buy", "sell", "trade"] },
  { label: "Net Worth", url: "/net-worth", keywords: ["wealth", "total"] },
  { label: "Dividends", url: "/dividends", keywords: ["income", "yield"] },
  { label: "Events", url: "/events", keywords: ["calendar", "corporate"] },
  { label: "Documents", url: "/documents", keywords: ["files", "reports"] },
  { label: "Watchlist", url: "/watchlist", keywords: ["watch"] },
  { label: "Import", url: "/import", keywords: ["csv", "upload"] },
  { label: "Pipeline", url: "/pipeline", keywords: ["jobs", "sync"] },
  { label: "Settings → General", url: "/settings?tab=general", keywords: ["display", "currency", "privacy", "profile"] },
  { label: "Settings → AI & LLM", url: "/settings?tab=ai", keywords: ["llm", "model", "ollama", "openai"] },
  { label: "Settings → Integrations", url: "/settings?tab=integrations", keywords: ["sec", "api", "key"] },
  { label: "Settings → Notifications", url: "/settings?tab=notifications", keywords: ["telegram", "alert"] },
  { label: "Settings → Schedule", url: "/settings?tab=schedule", keywords: ["cron", "price fetch"] },
  { label: "Settings → Platforms", url: "/settings?tab=platforms", keywords: ["broker", "color"] },
  { label: "AI Usage → Analyses", url: "/ai-usage?tab=analyses", keywords: ["llm cost", "spend", "analysis"] },
  { label: "AI Usage → Call Logs", url: "/ai-usage?tab=call-logs", keywords: ["logs", "tokens"] },
  { label: "AI Usage → Import Mapping", url: "/ai-usage?tab=import-mapping", keywords: ["import", "mapping"] },
];
