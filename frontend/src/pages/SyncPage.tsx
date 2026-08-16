import { useState } from "react";
import { ApiError } from "../api/client";
import { DateRangePicker, DateRange } from "../components/DateRangePicker";
import { useGmailStatus, useGmailSync, useStartRangeSync, useSyncTriggerStatus } from "../hooks/useGmailSync";
import {
  useAddBlacklistedSender,
  useBlacklistedSenders,
  useRemoveBlacklistedSender,
} from "../hooks/useBlacklist";
import { currentMonthRange } from "../lib/dateRange";

function errorMessage(err: Error | null): string | null {
  if (!err) return null;
  return err instanceof ApiError ? err.detail : "Sync failed. Please try again.";
}

export function SyncPage() {
  const { data: status, isLoading } = useGmailStatus();
  const sync = useGmailSync();
  const [range, setRange] = useState<DateRange>(currentMonthRange());

  const startRangeSync = useStartRangeSync();
  const [activeTriggerId, setActiveTriggerId] = useState<string | null>(null);
  const triggerStatus = useSyncTriggerStatus(activeTriggerId);

  const { data: blacklist } = useBlacklistedSenders();
  const addBlacklisted = useAddBlacklistedSender();
  const removeBlacklisted = useRemoveBlacklistedSender();
  const [newSender, setNewSender] = useState("");

  function handleAddBlacklisted() {
    const sender = newSender.trim();
    if (!sender) return;
    addBlacklisted.mutate(sender, { onSuccess: () => setNewSender("") });
  }

  function handleSyncRange() {
    startRangeSync.mutate(range, {
      onSuccess: (trigger) => setActiveTriggerId(trigger.id),
    });
  }

  const rangeSyncInProgress = triggerStatus.data?.status === "in_progress";

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-xl font-semibold text-gray-900">Sync Gmail</h1>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">Gmail Connection</h2>
        {isLoading ? (
          <p className="mt-2 text-sm text-gray-500">Loading...</p>
        ) : (
          <div className="mt-2 space-y-1 text-sm text-gray-600">
            <p>
              Status:{" "}
              <span className="font-medium">{status?.connected ? "connected" : "not connected"}</span>
            </p>
            <p>
              Synced mail range:{" "}
              <span className="font-medium">
                {status?.earliest_synced_at && status?.latest_synced_at
                  ? `${new Date(status.earliest_synced_at).toLocaleDateString()} – ${new Date(
                      status.latest_synced_at,
                    ).toLocaleDateString()}`
                  : "no mail synced yet"}
              </span>
            </p>
          </div>
        )}
        <button
          disabled
          title="Coming soon"
          className="mt-4 rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-400"
        >
          Disconnect Gmail (TODO)
        </button>
      </section>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">Sync now</h2>
        <p className="mt-1 text-sm text-gray-500">Fetch and classify your most recent Gmail messages.</p>
        <button
          onClick={() => sync.mutate(undefined)}
          disabled={sync.isPending}
          className="mt-3 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          {sync.isPending ? "Syncing..." : "Sync now"}
        </button>
        {sync.isSuccess && (
          <p className="mt-2 text-sm text-green-700">
            Fetched {sync.data.fetched} emails — {sync.data.extracted_accepted} accepted,{" "}
            {sync.data.extracted_needs_review} need review.
          </p>
        )}
        {sync.isError && <p className="mt-2 text-sm text-red-600">{errorMessage(sync.error)}</p>}
      </section>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">Sync a date range</h2>
        <p className="mt-1 text-sm text-gray-500">
          Backfill older mail from a specific window (up to 3 months at a time). Runs in the
          background — you can navigate away and come back.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <DateRangePicker value={range} onChange={setRange} />
          <button
            onClick={handleSyncRange}
            disabled={startRangeSync.isPending || rangeSyncInProgress}
            className="rounded-md border border-gray-900 px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-100 disabled:opacity-50"
          >
            {rangeSyncInProgress ? "In progress..." : "Sync range"}
          </button>
        </div>

        {rangeSyncInProgress && (
          <p className="mt-3 text-sm text-gray-600">
            Syncing {triggerStatus.data?.date_from} to {triggerStatus.data?.date_to}
            {" "}— this can take a while for large ranges.
          </p>
        )}
        {triggerStatus.data?.status === "success" && (
          <p className="mt-3 text-sm text-green-700">
            Synced {triggerStatus.data.date_from} to {triggerStatus.data.date_to}.
          </p>
        )}
        {triggerStatus.data?.status === "failed" && (
          <p className="mt-3 text-sm text-red-600">
            Sync failed: {triggerStatus.data.error ?? "unknown error"}
          </p>
        )}
        {startRangeSync.isError && (
          <p className="mt-3 text-sm text-red-600">{errorMessage(startRangeSync.error)}</p>
        )}
      </section>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">Blacklisted senders</h2>
        <p className="mt-1 text-sm text-gray-500">
          Emails from these senders are excluded at fetch time — never downloaded or stored.
          Use a full address (e.g. "newsletter@x.com") or a bare domain (e.g. "@x.com").
        </p>
        <div className="mt-3 flex gap-2">
          <input
            type="text"
            value={newSender}
            onChange={(e) => setNewSender(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddBlacklisted()}
            placeholder="sender@example.com or @example.com"
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
          <button
            onClick={handleAddBlacklisted}
            disabled={addBlacklisted.isPending || !newSender.trim()}
            className="rounded-md border border-gray-900 px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-100 disabled:opacity-50"
          >
            Add
          </button>
        </div>
        {addBlacklisted.isError && (
          <p className="mt-2 text-sm text-red-600">{errorMessage(addBlacklisted.error)}</p>
        )}

        {blacklist && blacklist.length > 0 ? (
          <ul className="mt-3 divide-y divide-gray-100">
            {blacklist.map((entry) => (
              <li key={entry.id} className="flex items-center justify-between py-2 text-sm">
                <span className="text-gray-700">{entry.sender}</span>
                <button
                  onClick={() => removeBlacklisted.mutate(entry.id)}
                  disabled={removeBlacklisted.isPending}
                  className="text-gray-400 hover:text-red-600 disabled:opacity-50"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-gray-500">No blacklisted senders yet.</p>
        )}
      </section>
    </div>
  );
}
