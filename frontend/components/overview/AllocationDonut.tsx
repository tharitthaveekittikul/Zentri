"use client";

import { PieChart as RechartsPieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { PieChart as PieChartIcon } from "lucide-react";
import { AllocationItem } from "@/lib/services/overview";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { useDualCurrency } from "@/hooks/useDualCurrency";

const COLORS = ["#6366f1", "#06b6d4", "#f59e0b", "#10b981", "#f43f5e", "#8b5cf6"];

interface Props {
  allocation: AllocationItem[];
}

export function AllocationDonut({ allocation }: Props) {
  const { format } = useDualCurrency();
  const data = allocation.map((a) => ({
    name: a.asset_type.replace("_", " ").toUpperCase(),
    value: Number(a.pct),
    rawValue: a.value,
  }));

  return (
    <div className="flex flex-col gap-2 h-full">
      <p className="text-sm font-medium">Allocation</p>
      {data.length === 0 ? (
        <div className="h-40 flex flex-col items-center justify-center gap-2 text-muted-foreground">
          <PieChartIcon className="h-6 w-6 opacity-30" />
          <span className="text-xs">No allocation data yet</span>
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={160}>
            <RechartsPieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                dataKey="value"
                paddingAngle={2}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} />
            </RechartsPieChart>
          </ResponsiveContainer>
          <div className="flex flex-col gap-1">
            {data.map((item, i) => (
              <div key={item.name} className="flex items-start justify-between text-xs">
                <div className="flex items-center gap-1">
                  <div
                    className="w-2 h-2 rounded-full mt-0.5"
                    style={{ background: COLORS[i % COLORS.length] }}
                  />
                  <span>{item.name}</span>
                </div>
                <div className="text-right">
                  <DualCurrencyAmount value={format(item.rawValue)} />
                  <span className="block text-xs text-muted-foreground">{item.value.toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
