"use client";

import { cn } from "@/lib/utils";
import { usePrivacyStore } from "@/store/privacy";
import { DualValue } from "@/hooks/useDualCurrency";

interface Props {
  value: DualValue;
  primaryClassName?: string;
  // inline=true: "1,234.56 THB (≈ 45.67 USD)" on one line — for table cells
  // inline=false (default): primary on top, secondary muted below — for cards/KPIs
  inline?: boolean;
}

export function DualCurrencyAmount({
  value,
  primaryClassName,
  inline = false,
}: Props) {
  const { isPrivate } = usePrivacyStore();

  const primaryDisplay = isPrivate
    ? `****** ${value.primaryCurrency}`
    : value.primary;

  const secondaryDisplay =
    value.secondary === null
      ? null
      : isPrivate
        ? `≈ ****** ${value.secondaryCurrency}`
        : value.secondary;

  if (inline) {
    return (
      <span className={cn("font-mono tabular-nums", primaryClassName)}>
        {primaryDisplay}
        {secondaryDisplay && (
          <span className="text-muted-foreground ml-1 text-xs">
            ({secondaryDisplay})
          </span>
        )}
      </span>
    );
  }

  return (
    <div>
      <span className={cn("font-mono tabular-nums", primaryClassName)}>
        {primaryDisplay}
      </span>
      {secondaryDisplay && (
        <p className="text-sm text-muted-foreground font-mono tabular-nums mt-0.5">
          {secondaryDisplay}
        </p>
      )}
    </div>
  );
}
