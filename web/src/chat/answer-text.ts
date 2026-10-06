// Pure helpers around an answer: splitting the text around its citation labels, and
// the plain-text version used by "copy with citations".

import type { AskResponse, Citation } from "../api/types.ts";

export type Segment = { kind: "text"; text: string } | { kind: "citation"; citation: Citation };

// Labels are matched literally; a label the model wrote but the server did not return
// stays plain text, so nothing clickable ever points at an unverified source.
export function splitAnswer(answer: string, citations: readonly Citation[]): Segment[] {
  const segments: Segment[] = [];
  let rest = answer;
  while (rest.length > 0) {
    let best: { index: number; citation: Citation } | null = null;
    for (const citation of citations) {
      const index = rest.indexOf(citation.label);
      if (index >= 0 && (best === null || index < best.index)) best = { index, citation };
    }
    if (!best) {
      segments.push({ kind: "text", text: rest });
      break;
    }
    if (best.index > 0) segments.push({ kind: "text", text: rest.slice(0, best.index) });
    segments.push({ kind: "citation", citation: best.citation });
    rest = rest.slice(best.index + best.citation.label.length);
  }
  return segments;
}

export interface CopyLabels {
  sources: string;
  aiNotice: string;
}

// The AI notice travels with the copied text: an answer pasted into an e-mail must
// still say where it came from.
export function formatForCopy(response: AskResponse, labels: CopyLabels): string {
  const lines = [response.answer.trim()];
  if (response.citations.length > 0) {
    lines.push("", labels.sources);
    for (const citation of response.citations) {
      lines.push(`- ${citation.label} ${citation.url}`);
    }
  }
  lines.push("", labels.aiNotice);
  return lines.join("\n");
}

export function formatDuration(ms: number, locale: string): string {
  const seconds = ms / 1000;
  const formatted = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(seconds);
  return `${formatted} s`;
}
