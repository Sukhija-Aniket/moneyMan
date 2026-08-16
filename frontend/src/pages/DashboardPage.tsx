import { useState } from "react";
import { ApiError } from "../api/client";
import { DateRangePicker, DateRange } from "../components/DateRangePicker";
import { SummaryCard } from "../components/SummaryCard";
import { CategoryBreakdownChart } from "../components/charts/CategoryBreakdownChart";
import { AccountBreakdownChart } from "../components/charts/AccountBreakdownChart";
import { BankBreakdownChart } from "../components/charts/BankBreakdownChart";
import { TrendChart } from "../components/charts/TrendChart";
import { useByAccount, useByBank, useByCategory, useOverview, useTrends } from "../hooks/useSummary";
import { currentMonthRange, formatMoney } from "../lib/dateRange";

function firstDateRangeError(...errors: (Error | null)[]): string | null {
  for (const err of errors) {
    if (err instanceof ApiError && err.status === 400) {
      return err.detail;
    }
  }
  return null;
}

export function DashboardPage() {
  const [range, setRange] = useState<DateRange>(currentMonthRange());

  const overview = useOverview(range);
  const byCategory = useByCategory(range);
  const byAccount = useByAccount(range);
  const byBank = useByBank(range);
  const trends = useTrends(6);

  const dateRangeError = firstDateRangeError(overview.error, byCategory.error, byAccount.error, byBank.error);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      {dateRangeError && (
        <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">{dateRangeError}</div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <SummaryCard
          label="Total Spend"
          value={overview.data ? formatMoney(overview.data.total_spend) : "..."}
          accent="negative"
        />
        <SummaryCard
          label="Total Income"
          value={overview.data ? formatMoney(overview.data.total_income) : "..."}
          accent="positive"
        />
        <SummaryCard
          label="Net"
          value={overview.data ? formatMoney(overview.data.net) : "..."}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-md border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-medium text-gray-700">By Category</h2>
          <CategoryBreakdownChart data={byCategory.data ?? []} />
        </div>
        <div className="rounded-md border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-medium text-gray-700">By Account</h2>
          <AccountBreakdownChart data={byAccount.data ?? []} />
        </div>
        <div className="rounded-md border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-medium text-gray-700">By Bank</h2>
          <BankBreakdownChart data={byBank.data ?? []} />
        </div>
        <div className="rounded-md border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-medium text-gray-700">Monthly Trend</h2>
          <TrendChart data={trends.data ?? []} />
        </div>
      </div>
    </div>
  );
}
