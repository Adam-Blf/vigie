// Citation panel. A native modal <dialog> gives the focus trap, Escape and the inert
// background for free; focus goes back to the citation button that opened it.

import { useEffect, useRef } from "preact/hooks";
import type { Citation } from "../api/types.ts";
import { useApp } from "../app/context.ts";
import { Icon } from "../ui/Icon.tsx";

interface CitationDialogProps {
  citation: Citation | null;
  corpusDate: string | null;
  onClose: () => void;
}

export function CitationDialog({ citation, corpusDate, onClose }: CitationDialogProps) {
  const { t, locale } = useApp();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (citation && !dialog.open) {
      openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
    } else if (!citation && dialog.open) {
      dialog.close();
    }
  }, [citation]);

  const handleClose = () => {
    onClose();
    openerRef.current?.focus();
  };

  const formattedDate = corpusDate
    ? new Intl.DateTimeFormat(locale, { dateStyle: "long" }).format(new Date(corpusDate))
    : null;

  return (
    <dialog
      ref={dialogRef}
      class="citation-dialog"
      aria-labelledby="citation-title"
      onClose={handleClose}
      onKeyDown={(event) => {
        // A modal dialog still lets Tab escape to the browser toolbar; keep it inside.
        if (event.key !== "Tab" || !dialogRef.current) return;
        const focusable = [...dialogRef.current.querySelectorAll<HTMLElement>("button, a[href]")];
        const first = focusable[0];
        const last = focusable.at(-1);
        if (!first || !last) return;
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }}
      onClick={(event) => {
        // A click on the backdrop lands on the dialog element itself.
        if (event.target === dialogRef.current) dialogRef.current?.close();
      }}
    >
      {citation && (
        <div class="citation-panel">
          <header class="citation-header">
            <h2 id="citation-title">{citation.label}</h2>
            <button
              type="button"
              class="icon-button"
              aria-label={t("citation.close")}
              onClick={() => dialogRef.current?.close()}
            >
              <Icon name="x" />
            </button>
          </header>
          <dl class="citation-facts">
            <div>
              <dt>{t("citation.regulation")}</dt>
              <dd>{citation.regulation}</dd>
            </div>
            <div>
              <dt>{t("citation.article")}</dt>
              <dd>{citation.article}</dd>
            </div>
            {citation.paragraph && (
              <div>
                <dt>{t("citation.paragraph")}</dt>
                <dd>{citation.paragraph}</dd>
              </div>
            )}
          </dl>
          <h3 class="citation-excerpt-title">{t("citation.excerpt")}</h3>
          <blockquote class="citation-excerpt" lang="fr">
            {citation.excerpt}
          </blockquote>
          {formattedDate && (
            <p class="citation-date">{t("citation.corpusDate", { date: formattedDate })}</p>
          )}
          <a class="button button-primary" href={citation.url} target="_blank" rel="noopener noreferrer">
            <Icon name="arrow-square-out" />
            <span>{t("citation.eurlex")}</span>
            <span class="sr-only"> {t("citation.newTab")}</span>
          </a>
        </div>
      )}
    </dialog>
  );
}
