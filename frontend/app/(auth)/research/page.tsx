"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { ExternalLinkIcon, NewspaperIcon, SearchIcon } from "lucide-react";
import { api } from "@/lib/api";

interface NewsArticle {
  id: string;
  symbol: string | null;
  title: string;
  url: string;
  source: string | null;
  summary: string | null;
  published_at: string | null;
  fetched_at: string;
}

async function fetchNewsLibrary(symbol?: string): Promise<NewsArticle[]> {
  const url = symbol
    ? `/api/v1/research/news?symbol=${encodeURIComponent(symbol)}&limit=100`
    : "/api/v1/research/news?limit=100";
  const r = await api.get(url);
  if (!r.ok) throw new Error("Failed to fetch news library");
  return r.json();
}

export default function ResearchPage() {
  const [filter, setFilter] = useState("");

  const { data: articles = [], isLoading } = useQuery({
    queryKey: ["research", "news"],
    queryFn: () => fetchNewsLibrary(),
    refetchOnWindowFocus: false,
  });

  const filtered = filter.trim()
    ? articles.filter(
        (a) =>
          a.title.toLowerCase().includes(filter.toLowerCase()) ||
          (a.symbol?.toLowerCase().includes(filter.toLowerCase())) ||
          (a.source?.toLowerCase().includes(filter.toLowerCase())),
      )
    : articles;

  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto">
      <PageHeader title="Research Library" />

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <NewspaperIcon className="size-4 text-primary" />
            News Index
          </CardTitle>
          <span className="text-xs text-muted-foreground">{articles.length} articles indexed</span>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="relative">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Filter by title, symbol, or source..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="pl-9"
            />
          </div>

          {isLoading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-16 rounded-lg" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              {articles.length === 0
                ? "No news indexed yet. Ask the chat assistant about a stock or topic to fetch news."
                : "No articles match your filter."}
            </div>
          ) : (
            <div className="divide-y">
              {filtered.map((article) => (
                <div key={article.id} className="py-3 space-y-0.5">
                  <div className="flex items-start justify-between gap-2">
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium hover:text-primary hover:underline flex-1 leading-snug"
                    >
                      {article.title}
                    </a>
                    <ExternalLinkIcon className="size-3.5 text-muted-foreground shrink-0 mt-0.5" />
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground flex-wrap">
                    {article.symbol && (
                      <span className="rounded bg-primary/10 text-primary px-1.5 py-0.5 font-mono font-medium">
                        {article.symbol}
                      </span>
                    )}
                    {article.source && <span>{article.source}</span>}
                    {article.published_at && (
                      <span>
                        {new Date(article.published_at).toLocaleDateString(undefined, {
                          dateStyle: "medium",
                        })}
                      </span>
                    )}
                  </div>
                  {article.summary && (
                    <p className="text-xs text-muted-foreground line-clamp-2 mt-1">{article.summary}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
