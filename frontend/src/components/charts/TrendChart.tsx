import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { TrendPoint } from "../../api/endpoints/summary";
import { formatMoney } from "../../lib/dateRange";

export function TrendChart({ data }: { data: TrendPoint[] }) {
  if (data.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-sm text-gray-400">
        No data available.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="period" />
        <YAxis />
        <Tooltip formatter={(value: number) => formatMoney(value)} />
        <Legend />
        <Line type="monotone" dataKey="total_spend" name="Spend" stroke="#dc2626" />
        <Line type="monotone" dataKey="total_income" name="Income" stroke="#16a34a" />
      </LineChart>
    </ResponsiveContainer>
  );
}
