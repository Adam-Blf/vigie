// Offline, 404 and server error: the owl, one sentence, and a way back.

import type { ComponentChildren } from "preact";
import { useState } from "preact/hooks";
import { useApp } from "../app/context.ts";
import { onLinkClick, ROUTES } from "../app/routes.ts";
import type { MessageKey } from "../i18n/fr.ts";
import { Mascot } from "../mascot/Mascot.tsx";
import type { MascotState } from "../mascot/state.ts";
import { Icon } from "../ui/Icon.tsx";

interface StatusProps {
  mascot: MascotState;
  title: MessageKey;
  body: MessageKey;
  children?: ComponentChildren;
}

function StatusScreen({ mascot, title, body, children }: StatusProps) {
  const { t } = useApp();
  return (
    <section class="status-screen" aria-labelledby="status-title">
      <Mascot state={mascot} size={160} />
      <h1 id="status-title">{t(title)}</h1>
      <p>{t(body)}</p>
      <div class="status-actions">{children}</div>
    </section>
  );
}

function BackToChat() {
  const { t } = useApp();
  return (
    <a class="button button-primary" href={ROUTES.chat} onClick={(e) => onLinkClick(e, ROUTES.chat)}>
      <Icon name="chat-circle-text" />
      <span>{t("notFound.back")}</span>
    </a>
  );
}

export function OfflineScreen() {
  const { t } = useApp();
  return (
    <StatusScreen mascot="error" title="offline.title" body="offline.body">
      <button type="button" class="button button-primary" onClick={() => window.location.reload()}>
        <Icon name="arrow-clockwise" />
        <span>{t("offline.retry")}</span>
      </button>
    </StatusScreen>
  );
}

export function NotFoundScreen() {
  return (
    <StatusScreen mascot="unknown" title="notFound.title" body="notFound.body">
      <BackToChat />
    </StatusScreen>
  );
}

// Only an id shaped like ours is shown, so the page cannot be made to display arbitrary text.
export function traceFromSearch(search: string): string | null {
  const trace = new URLSearchParams(search).get("trace");
  return trace && /^[A-Za-z0-9-]{1,64}$/.test(trace) ? trace : null;
}

export function ServerErrorScreen() {
  const { t } = useApp();
  const trace = traceFromSearch(window.location.search);
  const [copied, setCopied] = useState(false);
  return (
    <StatusScreen mascot="error" title="serverError.title" body="serverError.body">
      {trace && (
        <p class="trace">
          <code>{t("error.trace", { id: trace })}</code>
          <button
            type="button"
            class="button button-quiet"
            onClick={() => void navigator.clipboard.writeText(trace).then(() => setCopied(true))}
          >
            <Icon name={copied ? "check" : "copy"} />
            <span>{copied ? t("error.traceCopied") : t("error.copyTrace")}</span>
          </button>
        </p>
      )}
      <BackToChat />
    </StatusScreen>
  );
}
