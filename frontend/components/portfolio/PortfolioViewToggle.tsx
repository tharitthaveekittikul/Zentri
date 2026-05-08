"use client";

import { LayoutGrid, List, ScatterChart, Circle } from "lucide-react";
import { ViewMode } from "@/lib/visualizations/types";

interface Props {
  view: ViewMode;
  onChange: (view: ViewMode) => void;
}

const VIEWS: { mode: ViewMode; icon: React.ReactNode; label: string }[] = [
  { mode: "table", icon: <List className="h-4 w-4" />, label: "Table" },
  { mode: "grid", icon: <LayoutGrid className="h-4 w-4" />, label: "Grid" },
  { mode: "swarm", icon: <ScatterChart className="h-4 w-4" />, label: "Swarm" },
  { mode: "bubbles", icon: <Circle className="h-4 w-4" />, label: "Bubbles" },
];

export function PortfolioViewToggle({ view, onChange }: Props) {
  return (
    <div className="flex items-center gap-1 rounded-lg border border-border bg-muted/40 p-1">
      {VIEWS.map(({ mode, icon, label }) => (
        <button
          key={mode}
          onClick={() => onChange(mode)}
          title={label}
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            view === mode
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {icon}
          <span className="hidden sm:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}
