import { describe, expect, it, vi } from "vitest";
import { DEMO_FIXTURES, DEMO_USAGE } from "../demo/fixtures.ts";
import { createHttpClient, type FetchLike } from "./client.ts";
import { ApiError, kindForStatus, parseRetryAfter } from "./errors.ts";

const answer = DEMO_FIXTURES[0]!.response;

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

function client(fetchImpl: FetchLike, token: string | null = "vig_test") {
  return createHttpClient({ baseUrl: "/api/", getToken: () => token, fetchImpl });
}

const noop = { onToken: () => undefined };

describe("ask", () => {
  it("streams tokens then returns the final answer", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(
      sseResponse([
        'event: token\ndata: {"text":"Les "}\n\n',
        `event: token\ndata: {"text":"entités"}\n\nevent: final\ndata: ${JSON.stringify(answer)}\n\n`,
      ]),
    );
    const tokens: string[] = [];
    const result = await client(fetchImpl).ask(
      "question",
      { onToken: (t) => tokens.push(t) },
      new AbortController().signal,
    );
    expect(tokens).toEqual(["Les ", "entités"]);
    expect(result).toEqual(answer);
  });

  it("sends the token in the Authorization header only, never in the URL", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(Response.json(answer));
    await client(fetchImpl).ask("q", noop, new AbortController().signal);
    const [url, init] = fetchImpl.mock.calls[0]!;
    expect(url).toBe("/api/v1/ask");
    expect(url).not.toContain("vig_test");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer vig_test");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ question: "q" });
  });

  it("omits Authorization when there is no token", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(Response.json(answer));
    await client(fetchImpl, null).ask("q", noop, new AbortController().signal);
    expect(fetchImpl.mock.calls[0]![1].headers).not.toHaveProperty("Authorization");
  });

  it("maps HTTP failures to typed errors with trace id and Retry-After", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(
      Response.json(
        { detail: "slow down", trace_id: "t-429" },
        { status: 429, headers: { "Retry-After": "12" } },
      ),
    );
    const error = await client(fetchImpl)
      .ask("q", noop, new AbortController().signal)
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ kind: "rate_limited", status: 429, traceId: "t-429", retryAfterSeconds: 12 });
  });

  it("keeps the status when the error body is not JSON", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(
      new Response("<html>", { status: 502, headers: { "x-trace-id": "edge-1" } }),
    );
    const error = await client(fetchImpl).ask("q", noop, new AbortController().signal).catch((e: unknown) => e);
    expect(error).toMatchObject({ kind: "server", status: 502, traceId: "edge-1" });
  });

  it("turns a stream error event into a typed error", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(
      sseResponse(['event: error\ndata: {"status":503,"detail":"down","trace_id":"t-5"}\n\n']),
    );
    const error = await client(fetchImpl).ask("q", noop, new AbortController().signal).catch((e: unknown) => e);
    expect(error).toMatchObject({ kind: "server", status: 503, traceId: "t-5" });
  });

  it("fails clearly when the stream ends without a final answer", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(sseResponse(['event: token\ndata: {"text":"a"}\n\n']));
    const error = await client(fetchImpl).ask("q", noop, new AbortController().signal).catch((e: unknown) => e);
    expect(error).toMatchObject({ kind: "protocol" });
  });

  it("rejects a malformed JSON answer", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(Response.json({ answer: "x" }));
    const error = await client(fetchImpl).ask("q", noop, new AbortController().signal).catch((e: unknown) => e);
    expect(error).toMatchObject({ kind: "protocol" });
  });

  it("reports network failures and cancellations distinctly", async () => {
    const offline = vi.fn<FetchLike>().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(client(offline).ask("q", noop, new AbortController().signal)).rejects.toMatchObject({
      kind: "network",
    });
    const aborted = vi.fn<FetchLike>().mockRejectedValue(new DOMException("aborted", "AbortError"));
    await expect(client(aborted).ask("q", noop, new AbortController().signal)).rejects.toMatchObject({
      kind: "aborted",
    });
  });
});

describe("usage", () => {
  it("returns validated usage", async () => {
    const fetchImpl = vi.fn<FetchLike>().mockResolvedValue(Response.json(DEMO_USAGE));
    await expect(client(fetchImpl).usage(new AbortController().signal)).resolves.toEqual(DEMO_USAGE);
    expect(fetchImpl.mock.calls[0]![0]).toBe("/api/v1/usage/me");
  });

  it("maps 401 to unauthorized and rejects malformed payloads", async () => {
    const denied = vi.fn<FetchLike>().mockResolvedValue(new Response(null, { status: 401 }));
    await expect(client(denied).usage(new AbortController().signal)).rejects.toMatchObject({
      kind: "unauthorized",
    });
    const broken = vi.fn<FetchLike>().mockResolvedValue(Response.json({ questions_today: "7" }));
    await expect(client(broken).usage(new AbortController().signal)).rejects.toMatchObject({
      kind: "protocol",
    });
  });
});

describe("errors", () => {
  it("maps statuses to the places the UI shows them", () => {
    expect([401, 413, 422, 429, 500, 503].map(kindForStatus)).toEqual([
      "unauthorized",
      "too_large",
      "invalid",
      "rate_limited",
      "server",
      "server",
    ]);
  });

  it("reads Retry-After as seconds or as an HTTP date", () => {
    expect(parseRetryAfter("30")).toBe(30);
    expect(parseRetryAfter(null)).toBeNull();
    expect(parseRetryAfter("soon")).toBeNull();
    const now = Date.parse("2026-10-02T10:00:00Z");
    expect(parseRetryAfter("Fri, 02 Oct 2026 10:00:45 GMT", now)).toBe(45);
    expect(parseRetryAfter("Fri, 02 Oct 2026 09:00:00 GMT", now)).toBe(0);
  });
});
