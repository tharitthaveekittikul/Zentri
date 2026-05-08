"use client";

import { NetWorthChart } from "@/components/net-worth-chart";
import { PageHeader } from "@/components/layout/PageHeader";
import { usePrivacyStore } from "@/store/privacy";

export default function NetWorthPage() {
  const { isPrivate } = usePrivacyStore();
  return (
    <div className="space-y-6 min-h-0">
      <PageHeader title="Net Worth" />
      <div className="min-h-0">
        <NetWorthChart privacyMode={isPrivate} />
      </div>
    </div>
  );
}
