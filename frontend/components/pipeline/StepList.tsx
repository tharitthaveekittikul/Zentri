"use client";

import { useState } from "react";
import { type PipelineStep } from "@/lib/services/pipeline";

const STEP_LABELS: Record<string, string> = {
  fetch_and_store: "Fetch & Store",
  load_portfolio: "Load Portfolio",
  llm_call: "LLM Call",
  save_suggestions: "Save Suggestions",
  load_asset: "Load Asset",
  rag_retrieval: "RAG Retrieval",
  save_analysis: "Save Analysis",
  save_suggestion: "Save Suggestion",
  load_document: "Load Document",
  chunk_text: "Chunk Text",
  embed_store: "Embed & Store",
};

function stepDuration(step: PipelineStep): string {
  if (!step.finished_at) return "running…";
  const ms =
    new Date(step.finished_at).getTime() - new Date(step.started_at).getTime();
  return `${(ms / 1000).toFixed(1)}s`;
}

function StepIcon({ status }: { status: string }) {
  if (status === "done") return <span className="text-green-600 text-xs">✓</span>;
  if (status === "failed") return <span className="text-destructive text-xs">✗</span>;
  return <span className="text-blue-500 text-xs animate-pulse">●</span>;
}

function LLMMetadata({ m }: { m: Record<string, unknown> }) {
  const [showPrompt, setShowPrompt] = useState(false);
  const [showResponse, setShowResponse] = useState(false);

  return (
    <div className="space-y-1 ml-5">
      <div className="flex gap-3 text-xs text-muted-foreground flex-wrap">
        <span>↑{String(m.tokens_in)} / ↓{String(m.tokens_out)}</span>
        <span>${Number(m.cost_usd).toFixed(6)}</span>
        <span>฿{Number(m.cost_thb).toFixed(4)}</span>
        <span className="text-muted-foreground/60">
          {String(m.model)} · {String(m.provider)}
        </span>
      </div>
      <div className="flex gap-3">
        <button
          className="text-xs text-blue-500 underline underline-offset-2"
          onClick={() => setShowPrompt((v) => !v)}
        >
          Prompt {showPrompt ? "▴" : "▾"}
        </button>
        <button
          className="text-xs text-blue-500 underline underline-offset-2"
          onClick={() => setShowResponse((v) => !v)}
        >
          Response {showResponse ? "▴" : "▾"}
        </button>
      </div>
      {showPrompt && (
        <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-48 whitespace-pre-wrap font-mono">
          {String(m.prompt)}
        </pre>
      )}
      {showResponse && (
        <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-48 whitespace-pre-wrap font-mono">
          {String(m.response)}
        </pre>
      )}
    </div>
  );
}

function GenericMetadata({ m }: { m: Record<string, unknown> }) {
  const entries = Object.entries(m);
  if (entries.length === 0) return null;
  return (
    <p className="ml-5 text-xs text-muted-foreground">
      {entries.map(([k, v]) => `${k}: ${v}`).join(" · ")}
    </p>
  );
}

interface StepListProps {
  steps: PipelineStep[];
}

export function StepList({ steps }: StepListProps) {
  if (steps.length === 0) {
    return (
      <p className="text-xs text-muted-foreground py-2 ml-4">
        No step data recorded.
      </p>
    );
  }

  return (
    <div className="ml-4 border-l pl-4 py-2 space-y-2">
      {steps.map((step) => (
        <div key={step.id} className="space-y-1">
          <div className="flex items-center gap-2 text-sm">
            <StepIcon status={step.status} />
            <span className="font-medium">
              {STEP_LABELS[step.step_name] ?? step.step_name}
            </span>
            <span className="text-muted-foreground text-xs">
              {stepDuration(step)}
            </span>
          </div>
          {step.metadata &&
            (step.step_name === "llm_call" ? (
              <LLMMetadata m={step.metadata as Record<string, unknown>} />
            ) : (
              <GenericMetadata m={step.metadata as Record<string, unknown>} />
            ))}
          {step.error_message && (
            <p className="ml-5 text-xs text-destructive font-mono">
              {step.error_message}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
