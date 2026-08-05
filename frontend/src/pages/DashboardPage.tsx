import { useState } from "react";
import { DateRangePicker, DateRange } from "../components/DateRangePicker";
import { SummaryCard } from "../components/SummaryCard";
import { CategoryBreakdownChart } from "../components/charts/CategoryBreakdownChart";
import { AccountBreakdownChart } from "../components/charts/AccountBreakdownChart";
import { BankBreakdownChart } from "../components/charts/BankBreakdownChart";
import { TrendChart } from "../components/charts/TrendChart";
import { useByAccount, useByBank, useByCategory, useOverview, useTrends } from "../hooks/useSummary";
import { useGmailSync } from "../hooks/useGmailSync";
import { currentMonthRange, formatMoney } from "../lib/dateRange";

export function DashboardPage() {
  const [range, setRange] = useState<DateRange>(currentMonthRange());

  const overview = useOverview(range);
  const byCategory = useByCategory(range);
  const byAccount = useByAccount(range);
  const byBank = useByBank(range);
  const trends = useTrends(6);
  const sync = useGmailSync();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>
        <div className="flex items-center gap-3">
          <DateRangePicker value={range} onChange={setRange} />
          <button
            onClick={() => sync.mutate()}
            disabled={sync.isPending}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          >
            {sync.isPending ? "Syncing..." : "Sync now"}
          </button>
        </div>
      </div>

      {sync.isSuccess && (
        <div className="rounded-md bg-green-50 px-4 py-2 text-sm text-green-700">
          Synced {sync.data.synced_count} emails, found{" "}
          {sync.data.new_transactions_count} new transactions.
        </div>
      )}
      {sync.isError && (
        <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
          Sync failed. Please try again.
        </div>
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
