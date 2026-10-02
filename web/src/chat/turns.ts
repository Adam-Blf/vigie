// A turn is one question and what came back. History is display-only and lives in
// sessionStorage: the API never sees earlier turns, each question stands alone.

import type { ApiErrorKind } from "../api/errors.ts";
import { isAskResponse } from "../api/schema.ts";
import type { AskResponse } from "../api/types.ts";
import type { MascotSignals } from "../mascot/state.ts";
import { KEYS, readItem, removeItem, writeItem } from "../lib/storage.ts";

export interface TurnError {
  kind: ApiErrorKind;
  traceId: string | null;
  retryAfterSeconds: number | null;
}

export interface Turn {
  id: string;
  question: string;
  status: "pending" | "done" | "error" | "cancelled";
  streamed: string;
  response: AskResponse | null;
  error: TurnError | null;
}

const MAX_KEPT_TURNS = 50;

export function loadHistory(): Turn[] {
  const raw = readItem("session", KEYS.history);
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // A stored turn is re-validated: storage is writable by any script on the origin.
    return parsed.filter(
      (turn): turn is Turn =>
        typeof turn === "object" &&
        turn !== null &&
        typeof (turn as Turn).id === "string" &&
        typeof (turn as Turn).question === "string" &&
        ((turn as Turn).response === null || isAskResponse((turn as Turn).response)),
    );
  } catch {
    return [];
  }
}

export function saveHistory(turns: readonly Turn[]): void {
  // A pending turn would come back as a spinner that never ends, so only settled turns persist.
  const settled = turns.filter((turn) => turn.status !== "pending").slice(-MAX_KEPT_TURNS);
  writeItem("session", KEYS.history, JSON.stringify(settled));
}

export function clearHistory(): void {
  removeItem("session", KEYS.history);
}

const PROBLEM_KINDS: readonly ApiErrorKind[] = ["server", "network", "protocol"];

export function mascotSignals(
  turns: readonly Turn[],
  draft: string,
  online: boolean,
): MascotSignals {
  const last = turns.at(-1);
  // Once the person starts typing again, the last outcome no longer describes the moment.
  const outcome = draft.trim() === "" ? last : undefined;
  const response = outcome?.status === "done" ? outcome.response : null;
  return {
    error:
      !online ||
      (outcome?.status === "error" && outcome.error !== null && PROBLEM_KINDS.includes(outcome.error.kind)),
    blocked: response?.blocked === true,
    unknown: response !== null && !response.blocked && (response.refused || response.citations.length === 0),
    found: response !== null && !response.blocked && response.citations.length > 0,
    searching: last?.status === "pending",
    listening: draft.trim() !== "",
  };
}
