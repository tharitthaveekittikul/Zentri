import { ArrowUpRight, TrendingUp, TrendingDown } from "lucide-react";
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
        "bg-slate-50/50 dark:bg-slate-900 rounded-2xl p-5 shadow-sm border border-slate-100 dark:border-slate-800 relative group",
        onClick && "cursor-pointer hover:shadow-md transition-shadow duration-200",
        className
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-4">
        <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
          {title}
        </p>
        {onClick && (
          <ArrowUpRight
            className="h-4 w-4 text-slate-300 dark:text-slate-600 group-hover:text-slate-500 transition-colors"
            strokeWidth={1.5}
          />
        )}
      </div>

      <p className="text-2xl font-bold text-slate-900 dark:text-white tabular-nums tracking-tight">
        {value}
      </p>

      {trend !== undefined && (
        <div className="mt-3">
          <span
            className={cn(
              "inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full",
              isPositive
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400"
                : "bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-400"
            )}
          >
            {isPositive ? (
              <TrendingUp className="h-3 w-3" strokeWidth={2} />
            ) : (
              <TrendingDown className="h-3 w-3" strokeWidth={2} />
            )}
            {isPositive ? "+" : ""}
            {trend.toFixed(2)}%
          </span>
        </div>
      )}
    </div>
  );
}
