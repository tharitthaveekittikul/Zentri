"use client";

import { NetWorthChart } from "@/components/net-worth-chart";
import { PageHeader } from "@/components/layout/PageHeader";
import { usePrivacyStore } from "@/store/privacy";

export default function NetWorthPage() {
  const { isPrivate } = usePrivacyStore();
  return (
    <div className="space-y-6">
      <PageHeader title="Net Worth" />
      <NetWorthChart privacyMode={isPrivate} />
    </div>
  );
}
