// Chat state: turns, draft, streaming, cancellation and the error routing of brief 11.6
// (401 to the token prompt, 413 and 422 under the field, the rest inside the turn).

import { useEffect, useRef, useState } from "preact/hooks";
import { ApiError } from "../api/errors.ts";
import { MAX_QUESTION_CHARS } from "../api/types.ts";
import { useApp } from "../app/context.ts";
import { KEYS, readItem, writeItem } from "../lib/storage.ts";
import { clearToken, getToken } from "../lib/token.ts";
import { clearHistory, loadHistory, saveHistory, type Turn } from "./turns.ts";

// After this long, the person is told the search is slow and offered to cancel.
export const SLOW_AFTER_MS = 8000;
export const ASKED_EVENT = "vigie:asked";

function newId(): string {
  return typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function countQuestion(): void {
  const asked = Number(readItem("local", KEYS.questionsAsked) ?? "0") + 1;
  writeItem("local", KEYS.questionsAsked, String(asked));
  window.dispatchEvent(new CustomEvent(ASKED_EVENT, { detail: asked }));
}

export function useChat() {
  const { client, demo, t, noteAnswer } = useApp();
  const [turns, setTurns] = useState<Turn[]>(loadHistory);
  const [draft, setDraft] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [needToken, setNeedToken] = useState(false);
  const [slow, setSlow] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => saveHistory(turns), [turns]);
  useEffect(() => () => abortRef.current?.abort(), []);

  const patch = (id: string, change: Partial<Turn>) =>
    setTurns((all) => all.map((turn) => (turn.id === id ? { ...turn, ...change } : turn)));

  async function send(text?: string): Promise<void> {
    if (abortRef.current) return;
    const question = (text ?? draft).trim();
    if (!question) {
      setFieldError(t("chat.empty"));
      return;
    }
    if (question.length > MAX_QUESTION_CHARS) {
      setFieldError(t("error.invalid", { max: MAX_QUESTION_CHARS }));
      return;
    }
    if (!demo && !getToken()) {
      setNeedToken(true);
      setDraft(question);
      return;
    }
    const id = newId();
    const turn: Turn = { id, question, status: "pending", streamed: "", response: null, error: null };
    setTurns((all) => [...all, turn]);
    setDraft("");
    setFieldError(null);
    setNeedToken(false);
    const controller = new AbortController();
    abortRef.current = controller;
    const slowTimer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    let streamed = "";
    try {
      const response = await client.ask(
        question,
        {
          onToken: (piece) => {
            streamed += piece;
            patch(id, { streamed });
          },
        },
        controller.signal,
      );
      patch(id, { status: "done", response });
      noteAnswer(response);
      countQuestion();
    } catch (caught) {
      const error = caught instanceof ApiError ? caught : new ApiError("network", String(caught));
      if (error.kind === "aborted") {
        patch(id, { status: "cancelled" });
      } else if (error.kind === "too_large" || error.kind === "invalid") {
        // A rejected question goes back in the field with the reason underneath it.
        setTurns((all) => all.filter((item) => item.id !== id));
        setDraft(question);
        setFieldError(
          error.kind === "too_large" ? t("error.too_large") : t("error.invalid", { max: MAX_QUESTION_CHARS }),
        );
      } else {
        if (error.kind === "unauthorized") {
          clearToken();
          setNeedToken(true);
        }
        patch(id, {
          status: "error",
          error: { kind: error.kind, traceId: error.traceId, retryAfterSeconds: error.retryAfterSeconds },
        });
      }
    } finally {
      clearTimeout(slowTimer);
      setSlow(false);
      abortRef.current = null;
    }
  }

  return {
    turns,
    draft,
    setDraft: (value: string) => {
      setDraft(value);
      if (fieldError) setFieldError(null);
    },
    fieldError,
    needToken,
    tokenProvided: () => setNeedToken(false),
    slow,
    pending: turns.at(-1)?.status === "pending",
    send,
    cancel: () => abortRef.current?.abort(),
    reset: () => {
      abortRef.current?.abort();
      clearHistory();
      setTurns([]);
      setDraft("");
      setFieldError(null);
    },
  };
}
