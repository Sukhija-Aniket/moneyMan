export interface DateRange {
  date_from: string;
  date_to: string;
}

export function DateRangePicker({
  value,
  onChange,
}: {
  value: DateRange;
  onChange: (range: DateRange) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-sm text-gray-600">
        From
        <input
          type="date"
          value={value.date_from}
          onChange={(e) => onChange({ ...value, date_from: e.target.value })}
          className="ml-2 rounded-md border border-gray-300 px-2 py-1 text-sm"
        />
      </label>
      <label className="text-sm text-gray-600">
        To
        <input
          type="date"
          value={value.date_to}
          onChange={(e) => onChange({ ...value, date_to: e.target.value })}
          className="ml-2 rounded-md border border-gray-300 px-2 py-1 text-sm"
        />
      </label>
    </div>
  );
}
