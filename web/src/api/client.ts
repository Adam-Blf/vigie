// HTTP client for the real API. The token travels only in the Authorization header,
// never in a URL, so it cannot leak through history, logs or the Referer header.

import { ApiError, kindForStatus, parseRetryAfter } from "./errors.ts";
import { isAskResponse, isUsageResponse } from "./schema.ts";
import { createSseParser } from "./sse.ts";
import type { ApiClient, AskHandlers, AskResponse, UsageResponse } from "./types.ts";

export type FetchLike = (input: string, init: RequestInit) => Promise<Response>;

interface ClientOptions {
  baseUrl: string;
  getToken: () => string | null;
  fetchImpl?: FetchLike;
}

function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}${path}`;
}

async function failureFrom(response: Response): Promise<ApiError> {
  let detail = response.statusText || "request failed";
  let traceId = response.headers.get("x-trace-id");
  try {
    const body = (await response.json()) as Record<string, unknown>;
    if (typeof body.detail === "string") detail = body.detail;
    if (typeof body.trace_id === "string") traceId = body.trace_id;
  } catch {
    // Error bodies are best effort; the status code alone still tells the story.
  }
  return new ApiError(kindForStatus(response.status), detail, {
    status: response.status,
    traceId,
    retryAfterSeconds: parseRetryAfter(response.headers.get("retry-after")),
  });
}

function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof DOMException && error.name === "AbortError") {
    return new ApiError("aborted", "request cancelled");
  }
  return new ApiError("network", error instanceof Error ? error.message : "network error");
}

async function readStream(body: ReadableStream<Uint8Array>, handlers: AskHandlers): Promise<AskResponse> {
  const parser = createSseParser();
  const decoder = new TextDecoder();
  const reader = body.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    const events = done ? parser.flush() : parser.push(decoder.decode(value, { stream: true }));
    for (const event of events) {
      if (event.type === "token") handlers.onToken(event.text);
      if (event.type === "final") return event.response;
      if (event.type === "error") {
        throw new ApiError(event.status ? kindForStatus(event.status) : "protocol", event.detail, {
          status: event.status || null,
          traceId: event.traceId,
        });
      }
    }
    if (done) throw new ApiError("protocol", "stream ended without a final answer");
  }
}

export function createHttpClient(options: ClientOptions): ApiClient {
  const doFetch: FetchLike = options.fetchImpl ?? ((input, init) => fetch(input, init));

  function headers(extra: Record<string, string>): Record<string, string> {
    const token = options.getToken();
    return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
  }

  return {
    async ask(question, handlers, signal) {
      try {
        const response = await doFetch(joinUrl(options.baseUrl, "/v1/ask"), {
          method: "POST",
          headers: headers({ "Content-Type": "application/json", Accept: "text/event-stream" }),
          body: JSON.stringify({ question }),
          signal,
          cache: "no-store",
        });
        if (!response.ok) throw await failureFrom(response);
        const type = response.headers.get("content-type") ?? "";
        if (type.includes("text/event-stream") && response.body) {
          return await readStream(response.body, handlers);
        }
        const payload: unknown = await response.json();
        if (!isAskResponse(payload)) throw new ApiError("protocol", "malformed answer");
        return payload;
      } catch (error) {
        throw asApiError(error);
      }
    },

    async usage(signal): Promise<UsageResponse> {
      try {
        const response = await doFetch(joinUrl(options.baseUrl, "/v1/usage/me"), {
          method: "GET",
          headers: headers({ Accept: "application/json" }),
          signal,
          cache: "no-store",
        });
        if (!response.ok) throw await failureFrom(response);
        const payload: unknown = await response.json();
        if (!isUsageResponse(payload)) throw new ApiError("protocol", "malformed usage");
        return payload;
      } catch (error) {
        throw asApiError(error);
      }
    },
  };
}
