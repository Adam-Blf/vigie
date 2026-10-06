// Minimal Server-Sent Events reader for a fetch() body. EventSource cannot send an
// Authorization header or a POST body, so the stream is parsed by hand here.

import { isAskResponse } from "./schema.ts";
import type { StreamEvent } from "./types.ts";

interface RawEvent {
  event: string;
  data: string;
}

export interface SseParser {
  push(chunk: string): StreamEvent[];
  flush(): StreamEvent[];
}

function toStreamEvent(raw: RawEvent): StreamEvent | null {
  let payload: unknown;
  try {
    payload = JSON.parse(raw.data);
  } catch {
    return { type: "error", status: 0, detail: "malformed stream event", traceId: null };
  }
  const data = (typeof payload === "object" && payload !== null ? payload : {}) as Record<
    string,
    unknown
  >;
  switch (raw.event) {
    case "delta":
      return typeof data.text === "string" ? { type: "token", text: data.text } : null;
    case "answer":
      return isAskResponse(payload)
        ? { type: "final", response: payload }
        : { type: "error", status: 0, detail: "malformed final answer", traceId: null };
    case "error":
      return {
        type: "error",
        status: typeof data.status === "number" ? data.status : 500,
        detail: typeof data.error === "string" ? data.error : "server error",
        traceId: typeof data.trace_id === "string" ? data.trace_id : null,
      };
    default:
      // Unknown event names are a forward-compatible no-op, as the SSE spec intends.
      return null;
  }
}

export function createSseParser(): SseParser {
  let buffer = "";
  let current: RawEvent = { event: "message", data: "" };
  let hasData = false;

  function dispatchLine(line: string, out: StreamEvent[]): void {
    if (line === "") {
      if (hasData) {
        const parsed = toStreamEvent(current);
        if (parsed) out.push(parsed);
      }
      current = { event: "message", data: "" };
      hasData = false;
      return;
    }
    if (line.startsWith(":")) return;
    const colon = line.indexOf(":");
    const field = colon < 0 ? line : line.slice(0, colon);
    let value = colon < 0 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") current.event = value;
    if (field === "data") {
      current.data = hasData ? `${current.data}\n${value}` : value;
      hasData = true;
    }
  }

  return {
    push(chunk) {
      buffer += chunk;
      const out: StreamEvent[] = [];
      // A chunk may end between \r and \n, so a lone trailing \r stays in the buffer.
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";
      for (const line of lines) dispatchLine(line, out);
      return out;
    },
    flush() {
      const out: StreamEvent[] = [];
      if (buffer) dispatchLine(buffer, out);
      buffer = "";
      dispatchLine("", out);
      return out;
    },
  };
}
