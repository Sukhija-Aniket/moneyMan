export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }

  /** FastAPI error responses are `{ "detail": "..." }` — fall back to a generic message otherwise. */
  get detail(): string {
    const detail = (this.body as { detail?: unknown } | undefined)?.detail;
    return typeof detail === "string" ? detail : this.message;
  }
}

type QueryParams = object;

type RequestOptions<P extends QueryParams = QueryParams> = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  params?: P;
};

function buildUrl(path: string, params?: QueryParams): string {
  const url = new URL(path, API_BASE_URL);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

/**
 * Shared fetch wrapper. Always sends cookies (httpOnly session), never
 * touches any JS-accessible token storage.
 */
export async function apiFetch<T, P extends QueryParams = QueryParams>(
  path: string,
  options: RequestOptions<P> = {},
): Promise<T> {
  const { method = "GET", body, params } = options;

  const res = await fetch(buildUrl(path, params), {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let parsedBody: unknown;
    try {
      parsedBody = await res.json();
    } catch {
      // no body / not json
    }
    throw new ApiError(res.status, `Request to ${path} failed with ${res.status}`, parsedBody);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

/** Triggers a browser file download for an endpoint that returns a file (e.g. CSV export). */
export function buildDownloadUrl(path: string, params?: QueryParams): string {
  return buildUrl(path, params);
}
