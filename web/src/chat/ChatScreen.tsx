// Chat screen: empty state with examples, the conversation log, the composer docked at
// the bottom, the token prompt when needed, and the citation dialog.

import { useEffect, useRef, useState } from "preact/hooks";
import type { Citation } from "../api/types.ts";
import { useApp } from "../app/context.ts";
import { Mascot } from "../mascot/Mascot.tsx";
import { resolveMascotState } from "../mascot/state.ts";
import { useShownState } from "../mascot/useShownState.ts";
import { Icon } from "../ui/Icon.tsx";
import { TokenForm } from "../ui/TokenForm.tsx";
import { CitationDialog } from "./CitationDialog.tsx";
import { Composer } from "./Composer.tsx";
import { mascotSignals } from "./turns.ts";
import { TurnView } from "./TurnView.tsx";
import { useChat } from "./useChat.ts";

const EXAMPLES = ["chat.example.1", "chat.example.2", "chat.example.3", "chat.example.4"] as const;

export function ChatScreen() {
  const { t, online } = useApp();
  const chat = useChat();
  const [open, setOpen] = useState<{ citation: Citation; corpusDate: string | null } | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const mascotState = useShownState(resolveMascotState(mascotSignals(chat.turns, chat.draft, online)));
  const last = chat.turns.at(-1);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [chat.turns.length, last?.status]);

  // Only the settled answer is announced; streaming tokens would flood a screen reader.
  let announcement = "";
  if (last?.status === "done" && last.response) {
    announcement = last.response.blocked
      ? `${t("blocked.badge")}. ${t(`blocked.${last.response.block_reason ?? "other"}`)}`
      : last.response.answer;
  }

  const empty = chat.turns.length === 0;
  return (
    <div class={`chat${empty ? " chat-empty" : ""}`}>
      {empty ? (
        <section class="welcome" aria-labelledby="welcome-title">
          <Mascot state={mascotState} size={144} />
          <h1 id="welcome-title">{t("chat.title")}</h1>
          <p class="welcome-intro">{t("chat.intro")}</p>
          <p class="welcome-privacy">{t("chat.privacy")}</p>
          <h2 class="examples-title">{t("chat.examples")}</h2>
          <ul class="examples">
            {EXAMPLES.map((key) => (
              <li key={key}>
                <button type="button" class="example" onClick={() => void chat.send(t(key))}>
                  {t(key)}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <section class="conversation" aria-labelledby="conversation-title">
          <div class="conversation-head">
            <Mascot state={mascotState} size={64} />
            <div>
              <h1 id="conversation-title">{t("chat.log")}</h1>
              <p class="hint">{t("chat.history.note")}</p>
            </div>
            <button type="button" class="button button-quiet conversation-new" onClick={chat.reset}>
              <Icon name="note-pencil" />
              <span>{t("chat.new")}</span>
            </button>
          </div>
          <ol class="turns">
            {chat.turns.map((turn) => (
              <TurnView
                key={turn.id}
                turn={turn}
                onCite={(citation, corpusDate) => setOpen({ citation, corpusDate })}
                onRetry={(question) => void chat.send(question)}
              />
            ))}
          </ol>
          <div ref={logEndRef} />
        </section>
      )}
      <p class="sr-only" aria-live="polite">
        {announcement}
      </p>
      <div class="dock">
        {chat.needToken && (
          <section class="token-prompt" aria-labelledby="token-prompt-title">
            <h2 id="token-prompt-title">{t("token.title")}</h2>
            <p>{t("token.missing")}</p>
            <TokenForm idPrefix="chat" onSaved={chat.tokenProvided} />
          </section>
        )}
        <Composer
          draft={chat.draft}
          onDraft={chat.setDraft}
          onSend={() => void chat.send()}
          onCancel={chat.cancel}
          pending={chat.pending}
          slow={chat.slow}
          error={chat.fieldError}
        />
      </div>
      <CitationDialog
        citation={open?.citation ?? null}
        corpusDate={open?.corpusDate ?? null}
        onClose={() => setOpen(null)}
      />
    </div>
  );
}
