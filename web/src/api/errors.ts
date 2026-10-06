// One error type for every failure the chat has to explain to a person. The kind
// decides where the message goes: under the field, in the token prompt, or as a
// server error with a trace id someone can quote to us.

export type ApiErrorKind =
  | "unauthorized"
  | "too_large"
  | "invalid"
  | "rate_limited"
  | "server"
  | "network"
  | "aborted"
  | "protocol";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly traceId: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(
    kind: ApiErrorKind,
    message: string,
    options: { status?: number | null; traceId?: string | null; retryAfterSeconds?: number | null } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = options.status ?? null;
    this.traceId = options.traceId ?? null;
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
  }
}

export function kindForStatus(status: number): ApiErrorKind {
  if (status === 401) return "unauthorized";
  if (status === 413) return "too_large";
  if (status === 422) return "invalid";
  if (status === 429) return "rate_limited";
  return "server";
}

// Retry-After may be seconds or an HTTP date; anything else is ignored rather than guessed.
export function parseRetryAfter(value: string | null, now: number = Date.now()): number | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (/^\d+$/.test(trimmed)) return Number(trimmed);
  const date = Date.parse(trimmed);
  if (Number.isNaN(date)) return null;
  return Math.max(0, Math.ceil((date - now) / 1000));
}
