import { NetWorthChart } from "@/components/net-worth-chart";
import { PageHeader } from "@/components/layout/PageHeader";

export default function NetWorthPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Net Worth" />
      <NetWorthChart privacyMode={false} />
    </div>
  );
}
