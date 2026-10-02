// One exchange in the log: the question, then the streaming text, the answer, or the
// reason it failed.

import { useState } from "preact/hooks";
import type { Citation } from "../api/types.ts";
import { useApp } from "../app/context.ts";
import type { MessageKey } from "../i18n/fr.ts";
import { Icon } from "../ui/Icon.tsx";
import { AnswerBubble } from "./AnswerBubble.tsx";
import type { Turn, TurnError } from "./turns.ts";

interface TurnViewProps {
  turn: Turn;
  onCite: (citation: Citation, corpusDate: string | null) => void;
  onRetry: (question: string) => void;
}

export function TurnView({ turn, onCite, onRetry }: TurnViewProps) {
  const { t } = useApp();
  return (
    <li class="turn">
      <div class="bubble bubble-question">
        <span class="sr-only">{t("chat.you")} </span>
        {turn.question}
      </div>
      {turn.status === "pending" && (
        <div class="bubble bubble-answer bubble-pending" aria-busy="true">
          <span class="sr-only">{t("answer.streaming")}</span>
          {turn.streamed ? <p class="answer-text">{turn.streamed}</p> : <span class="typing" aria-hidden="true" />}
        </div>
      )}
      {turn.status === "done" && turn.response && (
        <AnswerBubble response={turn.response} onCite={onCite} />
      )}
      {turn.status === "cancelled" && <p class="turn-note">{t("chat.cancelled")}</p>}
      {turn.status === "error" && turn.error && (
        <ErrorBubble error={turn.error} onRetry={() => onRetry(turn.question)} />
      )}
    </li>
  );
}

function errorMessageKey(error: TurnError): MessageKey {
  switch (error.kind) {
    case "unauthorized":
      return "error.unauthorized";
    case "rate_limited":
      return error.retryAfterSeconds === null ? "error.rate_limited.later" : "error.rate_limited";
    case "network":
      return "error.network";
    case "protocol":
      return "error.protocol";
    default:
      return "error.server";
  }
}

function ErrorBubble({ error, onRetry }: { error: TurnError; onRetry: () => void }) {
  const { t } = useApp();
  const [copied, setCopied] = useState(false);
  const traceId = error.traceId;
  const copyTrace = async () => {
    if (!traceId) return;
    try {
      await navigator.clipboard.writeText(traceId);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div class="bubble bubble-answer bubble-error" role="alert">
      <p class="badge badge-warning">
        <Icon name="warning" />
        <span>{t(errorMessageKey(error), { seconds: error.retryAfterSeconds ?? 0 })}</span>
      </p>
      {traceId && (
        <p class="trace">
          <code>{t("error.trace", { id: traceId })}</code>
          <button type="button" class="button button-quiet" onClick={() => void copyTrace()}>
            <Icon name={copied ? "check" : "copy"} />
            <span>{copied ? t("error.traceCopied") : t("error.copyTrace")}</span>
          </button>
        </p>
      )}
      {error.kind !== "unauthorized" && (
        <button type="button" class="button button-quiet" onClick={onRetry}>
          <Icon name="arrow-clockwise" />
          <span>{t("offline.retry")}</span>
        </button>
      )}
    </div>
  );
}
