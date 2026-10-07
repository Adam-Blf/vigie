import { describe, expect, it } from "vitest";
import { DEMO_FIXTURES } from "../demo/fixtures.ts";
import { createSseParser } from "./sse.ts";

const final = DEMO_FIXTURES[0]?.response;

describe("createSseParser", () => {
  it("parses token and final events", () => {
    const parser = createSseParser();
    const events = parser.push(
      `event: delta\ndata: {"text":"Bon"}\n\nevent: delta\ndata: {"text":"jour"}\n\nevent: answer\ndata: ${JSON.stringify(final)}\n\n`,
    );
    expect(events.map((e) => e.type)).toEqual(["token", "token", "final"]);
    expect(events[0]).toEqual({ type: "token", text: "Bon" });
  });

  it("reassembles events split across chunks, including CRLF split in two", () => {
    const parser = createSseParser();
    expect(parser.push('event: delta\r\ndata: {"te')).toEqual([]);
    expect(parser.push('xt":"a"}\r')).toEqual([]);
    expect(parser.push("\n\r\n")).toEqual([{ type: "token", text: "a" }]);
  });

  it("joins multi-line data and ignores comments and unknown events", () => {
    const parser = createSseParser();
    const events = parser.push(': keep-alive\nevent: ping\ndata: {}\n\nevent: delta\ndata: {"text":\ndata: "x"}\n\n');
    expect(events).toEqual([{ type: "token", text: "x" }]);
  });

  it("turns server error events into error events with their trace id", () => {
    const parser = createSseParser();
    const events = parser.push('event: error\ndata: {"status":503,"error":"busy","trace_id":"t-1"}\n\n');
    expect(events).toEqual([{ type: "error", status: 503, detail: "busy", traceId: "t-1" }]);
  });

  it("reports malformed JSON and malformed final answers as errors", () => {
    const parser = createSseParser();
    const events = parser.push('event: delta\ndata: {nope\n\nevent: answer\ndata: {"answer":1}\n\n');
    expect(events.map((e) => e.type)).toEqual(["error", "error"]);
  });

  it("flushes a last event that had no trailing blank line", () => {
    const parser = createSseParser();
    expect(parser.push('event: delta\ndata: {"text":"z"}')).toEqual([]);
    expect(parser.flush()).toEqual([{ type: "token", text: "z" }]);
  });

  it("uses defaults for an error event without fields", () => {
    const parser = createSseParser();
    expect(parser.push("event: error\ndata: {}\n\n")).toEqual([
      { type: "error", status: 500, detail: "server error", traceId: null },
    ]);
  });
});
