import { NetWorthChart } from "@/components/net-worth-chart";

export default function NetWorthPage() {
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-xl font-semibold">Net Worth</h1>
      <NetWorthChart privacyMode={false} />
    </div>
  );
}
