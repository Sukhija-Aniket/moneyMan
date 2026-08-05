import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BankSummary } from "../../api/endpoints/summary";
import { formatMoney } from "../../lib/dateRange";

export function BankBreakdownChart({ data }: { data: BankSummary[] }) {
  if (data.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-sm text-gray-400">
        No data for this range.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="issuer_name" />
        <YAxis />
        <Tooltip formatter={(value: number) => formatMoney(value)} />
        <Bar dataKey="total_amount" fill="#16a34a" />
      </BarChart>
    </ResponsiveContainer>
  );
}
