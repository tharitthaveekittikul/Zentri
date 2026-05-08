"use client";

import { CoinsIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface SessionCost {
  costUsd: number;
  costThb?: number;
  messageCount: number;
}

interface ChatCostBadgeProps {
  session: SessionCost;
  className?: string;
}

export function ChatCostBadge({ session, className }: ChatCostBadgeProps) {
  if (session.messageCount === 0) return null;

  const formatUsd = (usd: number) =>
    usd < 0.001 ? "< $0.001" : `$${usd.toFixed(3)}`;

  const formatThb = (thb: number) =>
    thb < 0.1 ? "< ฿0.10" : `฿${thb.toFixed(2)}`;

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border bg-muted/60 px-2.5 py-1 text-[11px] text-muted-foreground",
        className,
      )}
    >
      <CoinsIcon className="size-3 text-amber-500 shrink-0" />
      <span>
        {formatUsd(session.costUsd)}
        {session.costThb !== undefined && session.costThb > 0
          ? ` / ${formatThb(session.costThb)}`
          : ""}
      </span>
      <span className="text-muted-foreground/60">· {session.messageCount} msg</span>
    </div>
  );
}
