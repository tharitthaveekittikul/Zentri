"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { usePrivacyStore } from "@/store/privacy";
import { useDualCurrency } from "@/hooks/useDualCurrency";

interface Analysis {
  id: string;
  verdict: "BUY" | "SELL" | "HOLD";
  target_price: number | null;
  reasoning: string;
  model: string;
  cost_usd: number;
  created_at: string;
}

interface VerdictCardProps {
  symbol: string;
}

const VERDICT_COLORS = {
  BUY: "bg-green-500 text-white",
  SELL: "bg-red-500 text-white",
  HOLD: "bg-yellow-500 text-white",
};

export function VerdictCard({ symbol }: VerdictCardProps) {
  const { isPrivate } = usePrivacyStore();
  const { formatNative } = useDualCurrency();
  const [latest, setLatest] = useState<Analysis | null>(null);
  const [history, setHistory] = useState<Analysis[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [conversation, setConversation] = useState<
    { role: string; content: string }[]
  >([]);
  const [convOpen, setConvOpen] = useState(false);
  const [initialized, setInitialized] = useState(false);

  const displayed = history.find((a) => a.id === selectedId) ?? latest;

  async function fetchLatest() {
    try {
      const res = await api.get(`/api/v1/analysis/${symbol}/latest`);
      const data = await res.json();
      setLatest(data);
      setSelectedId(data.id);
    } catch {}
  }

  async function fetchHistory() {
    try {
      const res = await api.get(`/api/v1/analysis/${symbol}/history`);
      setHistory(await res.json());
    } catch {}
  }

  async function runAnalysis() {
    setLoading(true);
    try {
      await api.post(`/api/v1/analysis/${symbol}`, null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to trigger analysis");
      setLoading(false);
      return;
    }

    const token = localStorage.getItem("access_token") ?? "";
    const source = new EventSource(`/api/v1/pipeline/stream?token=${token}`);
    source.onmessage = (e) => {
      const jobs = JSON.parse(e.data) as { job_type: string; status: string }[];
      const done = jobs.find(
        (j) => j.job_type === "run_analysis" && j.status === "done",
      );
      if (done) {
        source.close();
        fetchLatest().then(fetchHistory);
        setLoading(false);
        toast.success("Analysis complete");
      }
      const failed = jobs.find(
        (j) => j.job_type === "run_analysis" && j.status === "failed",
      );
      if (failed) {
        source.close();
        setLoading(false);
        toast.error("Analysis failed — check your LLM provider settings");
      }
    };
    source.onerror = () => {
      source.close();
      setLoading(false);
      toast.error("Lost connection to pipeline stream");
    };
  }

  async function loadConversation(id: string) {
    try {
      const res = await api.get(`/api/v1/analysis/conversation/${id}`);
      setConversation(await res.json());
    } catch {}
  }

  // Load latest on first render
  if (!initialized) {
    setInitialized(true);
    fetchLatest().then(fetchHistory);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">AI Analysis</CardTitle>
        <Button size="sm" onClick={runAnalysis} disabled={loading}>
          {loading ? "Analysing…" : "Run Analysis"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {displayed ? (
          <>
            <div className="flex items-center gap-3">
              <Badge className={VERDICT_COLORS[displayed.verdict]}>
                {displayed.verdict}
              </Badge>
              {displayed.target_price !== null && (
                <span className="text-sm text-muted-foreground">
                  Target:{" "}
                  {isPrivate
                    ? "••••"
                    : `${displayed.target_price.toFixed(2)} USD`}
                </span>
              )}
            </div>
            <p className="text-sm">{displayed.reasoning}</p>
            <p className="text-xs text-muted-foreground">
              {displayed.model} · {formatNative(displayed.cost_usd, "USD", 4).primary} ·{" "}
              {new Date(displayed.created_at).toLocaleDateString()}
            </p>

            {history.length > 1 && (
              <Select
                value={selectedId ?? ""}
                onValueChange={(v) => {
                  setSelectedId(v);
                  setConvOpen(false);
                }}
              >
                <SelectTrigger className="h-7 text-xs">
                  <SelectValue placeholder="Past verdicts" />
                </SelectTrigger>
                <SelectContent>
                  {history.map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.verdict} —{" "}
                      {new Date(a.created_at).toLocaleDateString()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            <Collapsible
              open={convOpen}
              onOpenChange={(o) => {
                setConvOpen(o);
                if (o && displayed) loadConversation(displayed.id);
              }}
            >
              <CollapsibleTrigger className="text-xs text-muted-foreground underline">
                {convOpen ? "Hide" : "View"} conversation
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2 space-y-1 max-h-64 overflow-y-auto">
                {conversation.map((m, i) => (
                  <div key={i} className="text-xs rounded p-2 bg-muted">
                    <span className="font-semibold capitalize">{m.role}: </span>
                    {m.content}
                  </div>
                ))}
              </CollapsibleContent>
            </Collapsible>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            No analysis yet. Click Run Analysis.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
