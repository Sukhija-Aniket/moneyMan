import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AccountSummary } from "../../api/endpoints/summary";
import { formatMoney } from "../../lib/dateRange";

export function AccountBreakdownChart({ data }: { data: AccountSummary[] }) {
  if (data.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-sm text-gray-400">
        No data for this range.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} layout="vertical" margin={{ left: 24 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" />
        <YAxis type="category" dataKey="display_name" width={140} />
        <Tooltip formatter={(value: number) => formatMoney(value)} />
        <Legend />
        <Bar dataKey="total_spend" name="Spend" fill="#dc2626" />
        <Bar dataKey="total_income" name="Income" fill="#16a34a" />
      </BarChart>
    </ResponsiveContainer>
  );
}
