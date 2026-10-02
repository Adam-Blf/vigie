// Question field. Enter sends, Shift+Enter breaks the line, and a key press that is
// part of an IME composition (Japanese, Chinese, accented dead keys) never sends.

import { useEffect, useRef } from "preact/hooks";
import { MAX_QUESTION_CHARS } from "../api/types.ts";
import { useApp } from "../app/context.ts";
import { Icon } from "../ui/Icon.tsx";

interface ComposerProps {
  draft: string;
  onDraft: (value: string) => void;
  onSend: () => void;
  onCancel: () => void;
  pending: boolean;
  slow: boolean;
  error: string | null;
}

export function Composer(props: ComposerProps) {
  const { t, locale } = useApp();
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const count = props.draft.length;
  const over = count > MAX_QUESTION_CHARS;
  const number = new Intl.NumberFormat(locale);

  // Grow with the text up to the CSS max-height, then scroll inside the field.
  useEffect(() => {
    const field = fieldRef.current;
    if (!field) return;
    field.style.height = "auto";
    field.style.height = `${field.scrollHeight}px`;
  }, [props.draft]);

  return (
    <form
      class="composer"
      onSubmit={(event) => {
        event.preventDefault();
        props.onSend();
      }}
    >
      {props.slow && (
        <p class="composer-slow" role="status">
          <span>{t("chat.slow")}</span>
          <button type="button" class="button button-quiet" onClick={props.onCancel}>
            <Icon name="stop" />
            <span>{t("chat.cancel")}</span>
          </button>
        </p>
      )}
      <label class="sr-only" for="question">
        {t("chat.input.label")}
      </label>
      <div class={`composer-box${props.error || over ? " is-invalid" : ""}`}>
        <textarea
          id="question"
          ref={fieldRef}
          rows={1}
          value={props.draft}
          placeholder={t("chat.input.placeholder")}
          aria-describedby="question-hint question-count question-error"
          aria-invalid={props.error || over ? "true" : "false"}
          enterkeyhint="send"
          onInput={(event) => props.onDraft(event.currentTarget.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
              event.preventDefault();
              props.onSend();
            }
          }}
        />
        <button
          type="submit"
          class="send-button"
          aria-label={t("chat.send")}
          disabled={props.pending}
        >
          <Icon name="paper-plane-right" />
        </button>
      </div>
      <div class="composer-foot">
        <p id="question-hint" class="composer-hint">
          {t("chat.input.hint")}
        </p>
        <p id="question-count" class={`composer-count${over ? " is-over" : ""}`}>
          {t("chat.counter", { count: number.format(count), max: number.format(MAX_QUESTION_CHARS) })}
        </p>
      </div>
      <p id="question-error" class="composer-error">
        {props.error}
      </p>
    </form>
  );
}
