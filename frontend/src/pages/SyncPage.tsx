import { useState } from "react";
import { ApiError } from "../api/client";
import { DateRangePicker, DateRange } from "../components/DateRangePicker";
import {
  useCurrentSync,
  useGmailStatus,
  useStartRangeSync,
  useSyncHistory,
  useSyncRequestStatus,
} from "../hooks/useGmailSync";
import { SyncRequestOut, SyncRequestStatus } from "../api/endpoints/gmail";
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

const REQUEST_STATUS_BADGE: Record<SyncRequestStatus, { label: string; className: string }> = {
  in_progress: { label: "In progress", className: "bg-blue-100 text-blue-700" },
  success: { label: "Success", className: "bg-green-100 text-green-700" },
  partial_failure: { label: "Partial failure", className: "bg-amber-100 text-amber-800" },
  failed: { label: "Failed", className: "bg-red-100 text-red-700" },
};

function SyncHistoryRow({ request }: { request: SyncRequestOut }) {
  const badge = REQUEST_STATUS_BADGE[request.status];
  return (
    <li className="py-2 text-sm">
      <div className="flex items-center justify-between">
        <span className="text-gray-700">
          {request.date_from} to {request.date_to}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{new Date(request.created_at).toLocaleString()}</span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}>
            {badge.label}
          </span>
        </div>
      </div>
      {request.segments.length > 0 && (
        <ul className="ml-4 mt-1 list-disc text-xs text-gray-500">
          {request.segments.map((segment) => (
            <li key={segment.id}>
              {segment.date_from} to {segment.date_to}: {segment.status}
              {segment.total_candidates !== null &&
                ` (${segment.processed_candidates}/${segment.total_candidates})`}
              {(segment.status === "failed" || segment.status === "extraction_failed") && segment.error
                ? ` — ${segment.error}`
                : ""}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function SyncPage() {
  const { data: status, isLoading } = useGmailStatus();
  const [range, setRange] = useState<DateRange>(currentMonthRange());

  const startRangeSync = useStartRangeSync();
  const [activeRequestId, setActiveRequestId] = useState<string | null>(null);
  const requestStatus = useSyncRequestStatus(activeRequestId);
  const currentSync = useCurrentSync();
  const syncHistory = useSyncHistory({ limit: 20 });

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
      onSuccess: (request) => setActiveRequestId(request.id),
      onSettled: () => {
        currentSync.refetch();
        syncHistory.refetch();
      },
    });
  }

  const rangeSyncInProgress =
    requestStatus.data?.status === "in_progress" || (currentSync.data?.in_progress ?? false);

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
            Syncing {requestStatus.data?.date_from ?? currentSync.data?.date_from} to{" "}
            {requestStatus.data?.date_to ?? currentSync.data?.date_to}
            {" "}— this can take a while for large ranges.
          </p>
        )}
        {requestStatus.data?.status === "success" && (
          <p className="mt-3 text-sm text-green-700">
            {requestStatus.data.segments.length === 0
              ? `${requestStatus.data.date_from} to ${requestStatus.data.date_to} was already fully synced.`
              : `Synced ${requestStatus.data.date_from} to ${requestStatus.data.date_to}.`}
          </p>
        )}
        {requestStatus.data?.status === "partial_failure" && (
          <div className="mt-3 space-y-1 text-sm">
            <p className="text-amber-700">
              Some parts of {requestStatus.data.date_from} to {requestStatus.data.date_to} didn't fully
              sync — re-run "Sync range" for the same dates to retry just those (already-fetched mail
              won't be re-downloaded, only reclassified).
            </p>
            <ul className="ml-4 list-disc text-gray-600">
              {requestStatus.data.segments.map((segment) => (
                <li key={segment.id}>
                  {segment.date_from} to {segment.date_to}: {segment.status}
                  {(segment.status === "failed" || segment.status === "extraction_failed") && segment.error
                    ? ` — ${segment.error}`
                    : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
        {requestStatus.data?.status === "failed" && (
          <p className="mt-3 text-sm text-red-600">
            Sync failed: {requestStatus.data.segments[0]?.error ?? "unknown error"}
          </p>
        )}
        {startRangeSync.isError && !rangeSyncInProgress && (
          <p className="mt-3 text-sm text-red-600">{errorMessage(startRangeSync.error)}</p>
        )}
      </section>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">Sync history</h2>
        <p className="mt-1 text-sm text-gray-500">
          Every range sync you've triggered — in progress, succeeded, partially failed, or failed.
        </p>
        {syncHistory.isLoading && <p className="mt-3 text-sm text-gray-500">Loading...</p>}
        {syncHistory.data && syncHistory.data.items.length > 0 ? (
          <ul className="mt-3 divide-y divide-gray-100">
            {syncHistory.data.items.map((request) => (
              <SyncHistoryRow key={request.id} request={request} />
            ))}
          </ul>
        ) : (
          !syncHistory.isLoading && <p className="mt-3 text-sm text-gray-500">No syncs yet.</p>
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
