"use client";

import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip";
import { InfoIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  MODEL_RECOMMENDATIONS,
  COST_TIER_LABELS,
} from "@/lib/modelRecommendations";
import { getPricingForModel } from "@/lib/llmPricing";

interface ModelTooltipProps {
  featureKey: string;
}

const COST_TIER_COLORS: Record<string, string> = {
  low: "text-emerald-600 dark:text-emerald-400",
  medium: "text-amber-600 dark:text-amber-400",
  high: "text-red-600 dark:text-red-400",
};

function PricingBadge({ model }: { model: string }) {
  const pricing = getPricingForModel(model);
  if (!pricing) return null;
  const fmt = (n: number) => (n < 1 ? `$${n}` : `$${n.toFixed(0)}`);
  return (
    <span className="ml-1.5 text-[10px] text-muted-foreground/70 font-mono whitespace-nowrap">
      {fmt(pricing.inputPerMToken)}/{fmt(pricing.outputPerMToken)} /1M
    </span>
  );
}

export function ModelTooltip({ featureKey }: ModelTooltipProps) {
  const rec = MODEL_RECOMMENDATIONS[featureKey];
  if (!rec) return null;

  return (
    <TooltipPrimitive.Provider delay={300}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger
          className="inline-flex items-center text-muted-foreground hover:text-foreground transition-colors outline-none"
          aria-label={`Model recommendation for ${featureKey}`}
        >
          <InfoIcon className="size-3.5" />
        </TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Positioner
            side="right"
            sideOffset={8}
            className="isolate z-50"
          >
            <TooltipPrimitive.Popup
              className={cn(
                "w-80 rounded-lg border bg-popover p-3 text-popover-foreground shadow-md text-xs",
                "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
                "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
              )}
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-sm">Recommended</span>
                  <span
                    className={cn(
                      "text-[11px] font-medium",
                      COST_TIER_COLORS[rec.cost_tier],
                    )}
                  >
                    {COST_TIER_LABELS[rec.cost_tier]}
                  </span>
                </div>
                <div className="flex items-center gap-1 flex-wrap">
                  <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-foreground">
                    {rec.recommended}
                  </code>
                  <PricingBadge model={rec.recommended} />
                </div>
                <p className="text-muted-foreground leading-relaxed">{rec.why}</p>
                {rec.alternatives.length > 0 && (
                  <div className="space-y-2 pt-1.5 border-t">
                    <p className="font-medium text-[11px] uppercase tracking-wide text-muted-foreground">
                      Alternatives
                    </p>
                    {rec.alternatives.map((alt) => (
                      <div key={alt.model} className="space-y-0.5">
                        <div className="flex items-center gap-1 flex-wrap">
                          <code className="font-mono text-[11px] text-foreground">
                            {alt.model}
                          </code>
                          <PricingBadge model={alt.model} />
                        </div>
                        <p className="text-muted-foreground">{alt.note}</p>
                      </div>
                    ))}
                  </div>
                )}
                <p className="text-[10px] text-muted-foreground/50 pt-0.5 border-t">
                  Pricing: input/output per 1M tokens
                </p>
              </div>
              <TooltipPrimitive.Arrow className="fill-popover [filter:drop-shadow(0_1px_0_var(--border))]" />
            </TooltipPrimitive.Popup>
          </TooltipPrimitive.Positioner>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
