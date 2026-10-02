import { beforeEach, describe, expect, it } from "vitest";
import type { AskResponse } from "../api/types.ts";
import { DEMO_FIXTURES } from "../demo/fixtures.ts";
import { formatDuration, formatForCopy, splitAnswer } from "./answer-text.ts";
import { clearHistory, loadHistory, mascotSignals, saveHistory, type Turn } from "./turns.ts";

const found = DEMO_FIXTURES.find((f) => f.id === "gdpr-breach")!.response;
const blocked = DEMO_FIXTURES.find((f) => f.id === "injection")!.response;
const refused = DEMO_FIXTURES.find((f) => f.id === "out-of-scope")!.response;

function turn(response: AskResponse | null, status: Turn["status"] = "done"): Turn {
  return { id: crypto.randomUUID(), question: "q", status, streamed: "", response, error: null };
}

describe("splitAnswer", () => {
  it("turns known labels into citation segments and keeps the rest as text", () => {
    const segments = splitAnswer(found.answer, found.citations);
    expect(segments.map((s) => s.kind)).toEqual(["text", "citation", "text"]);
    expect(segments[1]).toEqual({ kind: "citation", citation: found.citations[0] });
  });

  it("leaves a label the server did not return as plain text", () => {
    const segments = splitAnswer("Voir [DORA art. 99] et rien d'autre", found.citations);
    expect(segments).toEqual([{ kind: "text", text: "Voir [DORA art. 99] et rien d'autre" }]);
  });

  it("handles adjacent and repeated labels in reading order", () => {
    const [a, b] = DEMO_FIXTURES.slice(0, 2).map((f) => f.response.citations[0]!);
    const text = `${b!.label}${a!.label} puis ${b!.label}`;
    const kinds = splitAnswer(text, [a!, b!]).map((s) => (s.kind === "citation" ? s.citation.label : s.text));
    expect(kinds).toEqual([b!.label, a!.label, " puis ", b!.label]);
  });

  it("returns nothing for an empty answer", () => {
    expect(splitAnswer("", found.citations)).toEqual([]);
  });
});

describe("formatForCopy", () => {
  it("adds the sources and the AI notice to the copied text", () => {
    const text = formatForCopy(found, { sources: "Sources :", aiNotice: "Réponse générée par une IA." });
    expect(text).toContain(found.answer);
    expect(text).toContain(`- ${found.citations[0]!.label} ${found.citations[0]!.url}`);
    expect(text.endsWith("Réponse générée par une IA.")).toBe(true);
  });

  it("keeps the AI notice even without citations", () => {
    const text = formatForCopy(refused, { sources: "Sources :", aiNotice: "IA" });
    expect(text).not.toContain("Sources");
    expect(text.endsWith("IA")).toBe(true);
  });
});

describe("formatDuration", () => {
  it("formats milliseconds as seconds with the locale's decimal mark", () => {
    expect(formatDuration(1740, "fr")).toBe(`1,7${String.fromCharCode(0xa0)}s`);
    expect(formatDuration(85, "en")).toBe(`0.1${String.fromCharCode(0xa0)}s`);
  });
});

describe("mascotSignals", () => {
  it("reads the last outcome while the field is empty", () => {
    expect(mascotSignals([turn(found)], "", true)).toMatchObject({ found: true, unknown: false });
    expect(mascotSignals([turn(blocked)], "", true)).toMatchObject({ blocked: true, found: false });
    expect(mascotSignals([turn(refused)], "", true)).toMatchObject({ unknown: true });
  });

  it("forgets the outcome as soon as the person types again", () => {
    expect(mascotSignals([turn(blocked)], "nouvelle", true)).toMatchObject({
      blocked: false,
      listening: true,
    });
  });

  it("flags searching, network errors and offline", () => {
    expect(mascotSignals([turn(null, "pending")], "", true).searching).toBe(true);
    const failed: Turn = {
      ...turn(null, "error"),
      error: { kind: "network", traceId: null, retryAfterSeconds: null },
    };
    expect(mascotSignals([failed], "", true).error).toBe(true);
    const unauthorised: Turn = {
      ...turn(null, "error"),
      error: { kind: "unauthorized", traceId: null, retryAfterSeconds: null },
    };
    expect(mascotSignals([unauthorised], "", true).error).toBe(false);
    expect(mascotSignals([], "", false).error).toBe(true);
  });
});

describe("history", () => {
  beforeEach(() => sessionStorage.clear());

  it("round-trips settled turns and drops pending ones", () => {
    saveHistory([turn(found), turn(null, "pending")]);
    const loaded = loadHistory();
    expect(loaded).toHaveLength(1);
    expect(loaded[0]!.response).toEqual(found);
  });

  it("ignores corrupted or tampered storage", () => {
    sessionStorage.setItem("vigie.history", "{not json");
    expect(loadHistory()).toEqual([]);
    sessionStorage.setItem("vigie.history", JSON.stringify({ a: 1 }));
    expect(loadHistory()).toEqual([]);
    const tampered = { ...turn(found), response: { ...found, citations: [{ url: "javascript:alert(1)" }] } };
    sessionStorage.setItem("vigie.history", JSON.stringify([tampered]));
    expect(loadHistory()).toEqual([]);
  });

  it("clears on request", () => {
    saveHistory([turn(found)]);
    clearHistory();
    expect(loadHistory()).toEqual([]);
  });
});
