// One answer: blocked badge, text with clickable citations, AI notice, actions and the
// "version, model, duration" footer that makes a canary rollout visible to the eye.
// Model output only ever reaches the DOM as text nodes, never as HTML.

import { useState } from "preact/hooks";
import type { AskResponse, Citation } from "../api/types.ts";
import { useApp } from "../app/context.ts";
import { Icon } from "../ui/Icon.tsx";
import { formatDuration, formatForCopy, splitAnswer } from "./answer-text.ts";

interface AnswerBubbleProps {
  response: AskResponse;
  onCite: (citation: Citation, corpusDate: string | null) => void;
}

export function AnswerBubble({ response, onCite }: AnswerBubbleProps) {
  const { t } = useApp();
  const [copied, setCopied] = useState(false);
  const corpusDate = response.corpus_date ?? null;

  if (response.blocked) {
    const reason = response.block_reason ?? "other";
    return (
      <div class="bubble bubble-answer bubble-blocked">
        <p class="badge badge-danger">
          <Icon name="shield-warning" />
          <span>{t("blocked.badge")}</span>
        </p>
        <p>{t(`blocked.${reason}`)}</p>
        <Meta response={response} />
      </div>
    );
  }

  const unknown = response.refused || response.citations.length === 0;
  const copy = async () => {
    const text = formatForCopy(response, {
      sources: t("answer.sourcesCopy"),
      aiNotice: t("answer.aiNotice"),
    });
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };
  const removed = response.citations_removed ?? 0;
  const first = response.citations[0];

  return (
    <div class="bubble bubble-answer">
      {unknown && (
        <p class="badge badge-muted">
          <Icon name="book-open" />
          <span>{t("answer.unknown")}</span>
        </p>
      )}
      <p class="answer-text">
        {splitAnswer(response.answer, response.citations).map((segment, index) =>
          segment.kind === "text" ? (
            segment.text
          ) : (
            <button
              key={index}
              type="button"
              class="citation-chip"
              aria-label={t("citation.open", { label: segment.citation.label })}
              onClick={() => onCite(segment.citation, corpusDate)}
            >
              {segment.citation.label}
            </button>
          ),
        )}
      </p>
      {removed > 0 && (
        <p class="answer-note">
          <Icon name="warning" />
          <span>
            {removed === 1 ? t("answer.removed.one") : t("answer.removed.many", { count: removed })}
          </span>
        </p>
      )}
      <p class="answer-ai">{t("answer.aiNotice")}</p>
      <div class="answer-actions">
        <button type="button" class="button button-quiet" onClick={() => void copy()}>
          <Icon name={copied ? "check" : "copy"} />
          <span>{t("answer.copy")}</span>
        </button>
        {first && (
          <button type="button" class="button button-quiet" onClick={() => onCite(first, corpusDate)}>
            <Icon name="book-open" />
            <span>{t("answer.viewSource")}</span>
          </button>
        )}
        <span class="sr-only" role="status">
          {copied ? t("answer.copied") : ""}
        </span>
      </div>
      <Meta response={response} />
    </div>
  );
}

function Meta({ response }: { response: AskResponse }) {
  const { t, locale } = useApp();
  return (
    <p class="answer-meta">
      {t("answer.meta", {
        version: response.app_version,
        model: response.model,
        duration: formatDuration(response.latency_ms, locale),
      })}
    </p>
  );
}
