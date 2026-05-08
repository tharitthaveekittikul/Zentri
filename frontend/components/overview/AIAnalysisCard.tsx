"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BrainCircuitIcon, RefreshCwIcon, ZapIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  OverviewAnalysis,
  getLatestOverviewAnalysis,
  triggerOverviewAnalysis,
} from "@/lib/services/overview-analysis";
import { listFeatureConfigs } from "@/lib/services/feature-llm-config";
import { ConfirmLLMDialog } from "@/components/llm/ConfirmLLMDialog";
import { estimateCostUsd, getPricingForModel } from "@/lib/llmPricing";

const GRADE_COLORS: Record<string, string> = {
  A: "text-emerald-500",
  B: "text-green-500",
  C: "text-amber-500",
  D: "text-orange-500",
  F: "text-red-500",
};

const HEALTH_BADGE: Record<string, string> = {
  Excellent: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  Good: "bg-green-500/15 text-green-600 dark:text-green-400",
  Moderate: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  Weak: "bg-orange-500/15 text-orange-600 dark:text-orange-400",
  Critical: "bg-red-500/15 text-red-600 dark:text-red-400",
};

function ScoreRing({ score, grade }: { score: number; grade: string }) {
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center size-24">
      <svg className="size-24 -rotate-90" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={radius} fill="none" strokeWidth="8" className="stroke-muted" />
        <circle
          cx="48"
          cy="48"
          r={radius}
          fill="none"
          strokeWidth="8"
          strokeDasharray={`${progress} ${circumference}`}
          strokeLinecap="round"
          className={cn("transition-all duration-700", GRADE_COLORS[grade] ?? "text-primary", "stroke-current")}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("text-2xl font-bold", GRADE_COLORS[grade])}>{grade}</span>
        <span className="text-xs text-muted-foreground">{score}/100</span>
      </div>
    </div>
  );
}

function formatCostEstimate(model: string | undefined): string {
  if (!model || !getPricingForModel(model)) return "Cost varies by model";
  const usd = estimateCostUsd(model, 2000, 500);
  return usd < 0.01 ? `< $0.01` : `~$${usd.toFixed(3)}`;
}

export function AIAnalysisCard() {
  const [analysis, setAnalysis] = useState<OverviewAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingForce, setPendingForce] = useState(false);
  const [configuredModel, setConfiguredModel] = useState<string | undefined>();

  const fetchLatest = useCallback(async () => {
    try {
      const [data, configs] = await Promise.all([
        getLatestOverviewAnalysis(),
        listFeatureConfigs().catch(() => []),
      ]);
      setAnalysis(data);
      const cfg = configs.find((c) => c.feature_key === "overview_analysis");
      if (cfg?.model) setConfiguredModel(cfg.model);
    } catch {
      // no-op — will show empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLatest();
  }, [fetchLatest]);

  function requestRun(force = false) {
    setPendingForce(force);
    setConfirmOpen(true);
  }

  async function handleConfirmedRun() {
    setConfirmOpen(false);
    setRunning(true);
    setError(null);
    try {
      const result = await triggerOverviewAnalysis(pendingForce);
      setAnalysis(result);
    } catch (e: unknown) {
      const err = e as Error & { code?: string; lastAnalysis?: OverviewAnalysis };
      if (err.code === "cooldown_active" && err.lastAnalysis) {
        setAnalysis(err.lastAnalysis);
        setError("Recent analysis loaded. Use 'Re-analyze' to force a new one.");
      } else {
        setError(err.message ?? "Failed to run analysis");
      }
    } finally {
      setRunning(false);
    }
  }

  const runDate = analysis
    ? new Date(analysis.created_at).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <BrainCircuitIcon className="size-4 text-primary" />
          AI Portfolio Analysis
        </CardTitle>
        <div className="flex items-center gap-2">
          {analysis && (
            <Button
              size="sm"
              variant="ghost"
              disabled={running}
              onClick={() => requestRun(true)}
              className="gap-1.5 text-xs h-7"
            >
              <RefreshCwIcon className={cn("size-3", running && "animate-spin")} />
              Re-analyze
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center h-24 text-sm text-muted-foreground">
            Loading...
          </div>
        ) : !analysis ? (
          <div className="flex flex-col items-center gap-3 py-6">
            <p className="text-sm text-muted-foreground text-center">
              Get an AI-powered health check of your portfolio. No automatic scans — you control when it runs.
            </p>
            {error && <p className="text-xs text-destructive text-center">{error}</p>}
            <Button size="sm" disabled={running} onClick={() => requestRun()} className="gap-1.5">
              <ZapIcon className="size-3.5" />
              {running ? "Analyzing..." : "Run Analysis"}
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-start gap-4">
              <ScoreRing score={analysis.score} grade={analysis.grade} />
              <div className="flex-1 space-y-1.5 pt-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                      HEALTH_BADGE[analysis.health] ?? "bg-muted text-muted-foreground",
                    )}
                  >
                    {analysis.health}
                  </span>
                  {analysis.portfolio_adherence_pct !== null && (
                    <span className="text-xs text-muted-foreground">
                      {analysis.portfolio_adherence_pct}% target adherence
                    </span>
                  )}
                </div>
                <p className="text-xs font-medium text-foreground">Top action</p>
                <p className="text-sm text-muted-foreground">{analysis.top_action}</p>
              </div>
            </div>

            {analysis.insights.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-foreground">Insights</p>
                <ul className="space-y-1">
                  {analysis.insights.map((insight, i) => (
                    <li key={i} className="flex gap-2 text-sm text-muted-foreground">
                      <span className="mt-1.5 size-1.5 rounded-full bg-primary/50 shrink-0" />
                      {insight}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex items-center justify-between pt-1 border-t">
              <span className="text-[11px] text-muted-foreground">
                {analysis.model} · {runDate}
              </span>
              <div className="flex items-center gap-2">
                {error && <p className="text-xs text-amber-600 dark:text-amber-400">{error}</p>}
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={running}
                  onClick={() => requestRun()}
                  className="gap-1.5 text-xs h-6 px-2"
                >
                  <ZapIcon className="size-3" />
                  {running ? "Analyzing..." : "New analysis"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </CardContent>

      <ConfirmLLMDialog
        open={confirmOpen}
        title="Run Portfolio Analysis"
        description="The AI will analyze your portfolio allocation, performance, and risk."
        estimatedCost={formatCostEstimate(configuredModel ?? analysis?.model)}
        model={configuredModel ?? analysis?.model}
        loading={running}
        onConfirm={handleConfirmedRun}
        onCancel={() => setConfirmOpen(false)}
      />
    </Card>
  );
}
