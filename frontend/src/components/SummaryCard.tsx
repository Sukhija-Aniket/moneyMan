export function SummaryCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: "positive" | "negative" | "neutral";
}) {
  const accentClass =
    accent === "positive"
      ? "text-green-600"
      : accent === "negative"
        ? "text-red-600"
        : "text-gray-900";

  return (
    <div className="rounded-md border border-gray-200 bg-white p-4">
      <div className="text-sm text-gray-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${accentClass}`}>{value}</div>
    </div>
  );
}
