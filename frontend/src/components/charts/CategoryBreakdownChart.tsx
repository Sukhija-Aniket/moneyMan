import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { CategorySummary } from "../../api/endpoints/summary";
import { formatMoney } from "../../lib/dateRange";
import { CHART_COLORS } from "./colors";

export function CategoryBreakdownChart({ data }: { data: CategorySummary[] }) {
  if (data.length === 0) {
    return <EmptyState />;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          dataKey="total_amount"
          nameKey="category_name"
          cx="50%"
          cy="50%"
          outerRadius={100}
          label={(entry) => entry.category_name}
        >
          {data.map((entry, index) => (
            <Cell key={entry.category_id ?? entry.category_name} fill={CHART_COLORS[index % CHART_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(value: number) => formatMoney(value)} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

function EmptyState() {
  return (
    <div className="flex h-[300px] items-center justify-center text-sm text-gray-400">
      No data for this range.
    </div>
  );
}
