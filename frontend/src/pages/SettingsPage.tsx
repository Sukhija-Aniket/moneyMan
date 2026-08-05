import { useAuth } from "../hooks/useAuth";
import { useGmailStatus } from "../hooks/useGmailSync";

export function SettingsPage() {
  const { user } = useAuth();
  const { data: status, isLoading } = useGmailStatus();

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-xl font-semibold text-gray-900">Settings</h1>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">Account</h2>
        <p className="mt-2 text-sm text-gray-600">{user?.email}</p>
      </section>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">Gmail Connection</h2>
        {isLoading ? (
          <p className="mt-2 text-sm text-gray-500">Loading...</p>
        ) : (
          <div className="mt-2 space-y-1 text-sm text-gray-600">
            <p>
              Status: <span className="font-medium">{status?.status ?? "unknown"}</span>
            </p>
            <p>
              Last synced:{" "}
              <span className="font-medium">
                {status?.last_synced_at
                  ? new Date(status.last_synced_at).toLocaleString()
                  : "never"}
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
    </div>
  );
}
