import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { CategorySummary } from "../../api/endpoints/summary";
import { formatMoney } from "../../lib/dateRange";
import { CHART_COLORS } from "./colors";

export function CategoryBreakdownChart({ data }: { data: CategorySummary[] }) {
  // Spend only — income is almost never meaningfully split across categories (it's
  // typically just "Income"), so this chart answers "where did the money go."
  const spendData = data.filter((d) => d.total_spend > 0);

  if (spendData.length === 0) {
    return <EmptyState />;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={spendData}
          dataKey="total_spend"
          nameKey="category_name"
          cx="50%"
          cy="50%"
          outerRadius={100}
          label={(entry) => entry.category_name}
        >
          {spendData.map((entry, index) => (
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
