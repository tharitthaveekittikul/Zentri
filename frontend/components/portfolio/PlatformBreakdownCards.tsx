"use client";

import { useMemo, useState } from "react";
import { ArrowUpRight, ArrowDownRight, ChevronDown } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { HoldingRow, groupHoldingsByPlatform } from "@/lib/services/portfolio";

interface Props {
  holdings: HoldingRow[];
}

export function PlatformBreakdownCards({ holdings }: Props) {
  const { formatNative } = useDualCurrency();
  const groups = useMemo(() => groupHoldingsByPlatform(holdings), [holdings]);
  const [open, setOpen] = useState(true);

  if (groups.length === 0) return null;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="group flex items-center gap-1.5">
        <span className="text-[11px] font-medium tracking-[0.08em] uppercase text-muted-foreground transition-colors group-hover:text-foreground">
          By Platform
        </span>
        <ChevronDown
          className={`h-3 w-3 text-muted-foreground transition-transform duration-200 group-hover:text-foreground ${open ? "rotate-0" : "-rotate-90"}`}
        />
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="flex gap-3 overflow-x-auto pb-1 pt-3">
          {groups.map((group) => {
            const hasCurrencyData = group.currencyGroups.some(
              (cg) => cg.totalValue != null || cg.totalPnl != null,
            );
            return (
              <div
                key={group.platform}
                title={group.platform}
                className="card-surface flex min-h-[108px] min-w-[168px] flex-shrink-0 flex-col gap-2.5 rounded-2xl border border-border bg-card p-4"
              >
                {/* Header row: name + count badge */}
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-[10px] font-medium uppercase tracking-[0.07em] text-muted-foreground">
                    {group.platform}
                  </span>
                  <span className="shrink-0 rounded-full bg-muted px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-muted-foreground">
                    {group.count}
                  </span>
                </div>

                {/* Currency data */}
                {hasCurrencyData ? (
                  group.currencyGroups.map((cg) => {
                    const pnlPositive = (cg.totalPnl ?? 0) >= 0;
                    const pnlColor = pnlPositive
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-destructive";
                    return (
                      <div key={cg.currency} className="flex flex-col gap-1">
                        {cg.totalValue != null ? (
                          <DualCurrencyAmount
                            value={formatNative(
                              String(cg.totalValue),
                              cg.currency,
                            )}
                            primaryClassName="text-sm font-semibold font-mono tabular-nums"
                            secondaryClassName="text-[11px] font-mono tabular-nums text-muted-foreground mt-0.5"
                          />
                        ) : (
                          <span className="font-mono text-sm tabular-nums text-muted-foreground">
                            —
                          </span>
                        )}
                        {cg.totalPnl != null ? (
                          <div
                            className={`flex items-center gap-0.5 ${pnlColor}`}
                          >
                            <DualCurrencyAmount
                              value={formatNative(
                                String(cg.totalPnl),
                                cg.currency,
                                2,
                                true,
                              )}
                              primaryClassName={`text-xs font-mono tabular-nums ${pnlColor}`}
                              secondaryClassName={`text-[11px] font-mono tabular-nums ${pnlColor} opacity-60 mt-0.5`}
                            />
                          </div>
                        ) : null}
                      </div>
                    );
                  })
                ) : (
                  <div className="flex flex-1 flex-col justify-end">
                    <span className="font-mono text-sm tabular-nums text-muted-foreground/50">
                      No price data
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
