import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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
        <Legend />
        <Bar dataKey="total_spend" name="Spend" fill="#dc2626" />
        <Bar dataKey="total_income" name="Income" fill="#16a34a" />
      </BarChart>
    </ResponsiveContainer>
  );
}
