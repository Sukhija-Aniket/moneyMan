export function Pagination({
  limit,
  offset,
  total,
  onOffsetChange,
}: {
  limit: number;
  offset: number;
  total: number;
  onOffsetChange: (offset: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const page = Math.floor(offset / limit) + 1;

  return (
    <div className="flex items-center justify-between py-3 text-sm text-gray-600">
      <span>
        Page {page} of {totalPages} ({total} total)
      </span>
      <div className="flex gap-2">
        <button
          disabled={offset <= 0}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
          className="rounded-md border border-gray-300 px-3 py-1 disabled:opacity-40"
        >
          Previous
        </button>
        <button
          disabled={page >= totalPages}
          onClick={() => onOffsetChange(offset + limit)}
          className="rounded-md border border-gray-300 px-3 py-1 disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}
