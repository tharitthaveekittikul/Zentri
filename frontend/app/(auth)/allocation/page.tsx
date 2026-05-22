"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAllocationHoldings, HoldingAllocationItem } from "@/lib/services/overview";
import { AllocationDrillDonut } from "@/components/allocation/AllocationDrillDonut";
import { AllocationTable } from "@/components/allocation/AllocationTable";

function groupKey(h: HoldingAllocationItem, tab: "type" | "sector"): string {
  return tab === "type" ? h.asset_type.replace(/_/g, " ").toUpperCase() : h.sector;
}

export default function AllocationPage() {
  const [tab, setTab] = useState<"type" | "sector">("type");
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const { data: holdings = [] } = useQuery({
    queryKey: ["allocation", "holdings"],
    queryFn: fetchAllocationHoldings,
  });

  const tableHoldings = selectedGroup
    ? holdings.filter((h) => groupKey(h, tab) === selectedGroup)
    : holdings;

  function handleTabChange(newTab: "type" | "sector") {
    setTab(newTab);
    setSelectedGroup(null);
    setSortDir("desc");
  }

  function handleSelectGroup(group: string) {
    setSelectedGroup(group);
    setSortDir("desc");
  }

  function handleClearGroup() {
    setSelectedGroup(null);
    setSortDir("desc");
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Allocation</h1>
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        <div className="w-full lg:w-[380px] shrink-0 bg-card rounded-2xl p-6 border border-border">
          <AllocationDrillDonut
            holdings={holdings}
            tab={tab}
            onTabChange={handleTabChange}
            selectedGroup={selectedGroup}
            onSelectGroup={handleSelectGroup}
            onClearGroup={handleClearGroup}
          />
        </div>
        <div className="flex-1 min-w-0 bg-card rounded-2xl p-6 border border-border">
          <p className="text-sm font-medium mb-4">
            {selectedGroup ? selectedGroup : "All Holdings"}
          </p>
          <AllocationTable holdings={tableHoldings} sortDir={sortDir} onSortDirChange={setSortDir} />
        </div>
      </div>
    </div>
  );
}
