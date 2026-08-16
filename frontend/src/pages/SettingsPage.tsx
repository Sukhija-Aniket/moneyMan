import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import type { LlmProvider } from "../api/endpoints/auth";
import { useAuth, useAvailableTimezones, useUpdateUserSettings } from "../hooks/useAuth";

const PROVIDER_OPTIONS: { value: LlmProvider; label: string; description: string }[] = [
  {
    value: "anthropic",
    label: "Claude (Anthropic)",
    description: "Hosted, no setup required.",
  },
  {
    value: "ollama",
    label: "Ollama (local)",
    description: "Runs on your machine via a local Ollama server — requires `ollama serve` running.",
  },
];

export function SettingsPage() {
  const { user } = useAuth();
  const updateSettings = useUpdateUserSettings();
  const { data: timezoneOptions } = useAvailableTimezones();

  const [llmProvider, setLlmProvider] = useState<LlmProvider | null>(null);
  const [tz, setTz] = useState<string | null>(null);

  // Seed local form state from the loaded user once, and whenever a save completes
  // (so the form reflects the saved values, not stale pre-save selections).
  useEffect(() => {
    if (user) {
      setLlmProvider(user.llm_provider);
      setTz(user.timezone);
    }
  }, [user?.llm_provider, user?.timezone]);

  const isDirty = user != null && (llmProvider !== user.llm_provider || tz !== user.timezone);

  function handleSave() {
    if (!isDirty || llmProvider === null || tz === null) return;
    updateSettings.mutate({ llm_provider: llmProvider, timezone: tz });
  }

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-xl font-semibold text-gray-900">Settings</h1>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">Account</h2>
        <p className="mt-2 text-sm text-gray-600">{user?.email}</p>
      </section>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">AI Provider</h2>
        <p className="mt-1 text-sm text-gray-500">
          Choose which AI provider classifies and extracts your transactions.
        </p>
        <div className="mt-3 space-y-2">
          {PROVIDER_OPTIONS.map((option) => (
            <label
              key={option.value}
              className="flex items-start gap-3 rounded-md border border-gray-200 p-3 text-sm hover:bg-gray-50"
            >
              <input
                type="radio"
                name="llm_provider"
                value={option.value}
                checked={llmProvider === option.value}
                onChange={() => setLlmProvider(option.value)}
                className="mt-0.5"
              />
              <span>
                <span className="block font-medium text-gray-900">{option.label}</span>
                <span className="block text-gray-500">{option.description}</span>
              </span>
            </label>
          ))}
        </div>
      </section>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">Timezone</h2>
        <p className="mt-1 text-sm text-gray-500">
          Used to determine "today" for date-range validation (e.g. sync and dashboard filters).
        </p>
        <select
          value={tz ?? ""}
          onChange={(e) => setTz(e.target.value)}
          disabled={!timezoneOptions}
          className="mt-3 w-full rounded-md border border-gray-300 px-3 py-2 text-sm disabled:opacity-50"
        >
          {/* Guards against a previously-saved value the backend's tzdata no longer
              recognizes (e.g. a deprecated alias like "Asia/Calcutta") — keeps it selectable
              rather than silently switching the dropdown to a blank/different value. */}
          {tz && timezoneOptions && !timezoneOptions.includes(tz) && (
            <option value={tz}>{tz} (unrecognized)</option>
          )}
          {(timezoneOptions ?? (tz ? [tz] : [])).map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </section>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={!isDirty || updateSettings.isPending}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          {updateSettings.isPending ? "Saving..." : "Save"}
        </button>
        {updateSettings.isSuccess && !isDirty && (
          <span className="text-sm text-green-700">Saved.</span>
        )}
        {updateSettings.isError && (
          <span className="text-sm text-red-600">
            {updateSettings.error instanceof ApiError
              ? updateSettings.error.detail
              : "Failed to save settings. Try again."}
          </span>
        )}
      </div>
    </div>
  );
}
