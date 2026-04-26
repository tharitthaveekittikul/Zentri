"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { AllocationItem } from "@/lib/services/overview";
import { PrivacyValue } from "@/components/ui/PrivacyValue";

const COLORS = ["#6366f1", "#06b6d4", "#f59e0b", "#10b981", "#f43f5e", "#8b5cf6"];

interface Props {
  allocation: AllocationItem[];
}

export function AllocationDonut({ allocation }: Props) {
  const data = allocation.map((a) => ({
    name: a.asset_type.replace("_", " ").toUpperCase(),
    value: Number(a.pct),
    rawValue: a.value,
  }));

  return (
    <div className="flex flex-col gap-2 h-full">
      <p className="text-sm font-medium">Allocation</p>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">No holdings with price data yet.</p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
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
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-col gap-1">
            {data.map((item, i) => (
              <div key={item.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ background: COLORS[i % COLORS.length] }}
                  />
                  <span>{item.name}</span>
                </div>
                <span className="text-muted-foreground">
                  <PrivacyValue
                    value={`$${Number(item.rawValue).toLocaleString("en-US", {
                      maximumFractionDigits: 0,
                    })} (${item.value.toFixed(1)}%)`}
                  />
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
