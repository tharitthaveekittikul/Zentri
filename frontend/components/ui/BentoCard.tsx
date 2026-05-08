import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface BentoCardProps {
  title: string;
  value: string;
  trend?: number;
  className?: string;
  onClick?: () => void;
}

export function BentoCard({ title, value, trend, className, onClick }: BentoCardProps) {
  const isPositive = trend !== undefined && trend >= 0;

  return (
    <div
      className={cn(
        "bg-page dark:bg-slate-900 rounded-2xl p-5 shadow-sm relative group",
        onClick && "cursor-pointer hover:shadow-md transition-shadow duration-200",
        className
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-4">
        <p className="text-[11px] font-semibold text-ink-muted/50 dark:text-ink-muted/40 uppercase tracking-widest">
          {title}
        </p>
        {onClick && (
          <ArrowUpRight
            className="h-4 w-4 text-slate-300 dark:text-slate-600 group-hover:text-slate-500 transition-colors"
            strokeWidth={1.5}
          />
        )}
      </div>

      <p className="text-2xl font-bold text-ink dark:text-ink tabular-nums tracking-tight">
        {value}
      </p>

      {trend !== undefined && (
        <div className="mt-3">
          <span
            className={cn(
              "inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full",
              isPositive
                ? "bg-brand-accent/10 text-brand-mid dark:bg-brand-accent/15 dark:text-brand-sage"
                : "bg-brand-danger/10 text-brand-danger dark:bg-brand-danger/15 dark:text-brand-danger"
            )}
          >
            {isPositive ? (
              <ArrowUpRight className="h-3 w-3" strokeWidth={2} />
            ) : (
              <ArrowDownRight className="h-3 w-3" strokeWidth={2} />
            )}
            {Math.abs(trend).toFixed(2)}%
          </span>
        </div>
      )}
    </div>
  );
}
