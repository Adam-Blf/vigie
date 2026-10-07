// The API contract as the interface sees it (brief 11.6). The server side lives in
// src/vigie/api; when docs/openapi.json lands, these shapes are checked against it.

// Mirrors VIGIE_MAX_QUESTION_CHARS on the server; checked here only to explain the limit early.
export const MAX_QUESTION_CHARS = 2000;

export const BLOCK_REASONS = ["injection", "jailbreak", "prompt_leak", "pii", "other"] as const;
export type BlockReason = (typeof BLOCK_REASONS)[number];

export interface Citation {
  label: string;
  regulation: string;
  article: string;
  paragraph: string | null;
  excerpt: string;
  url: string;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
  blocked: boolean;
  block_reason: BlockReason | null;
  refused: boolean;
  trace_id: string;
  app_version: string;
  bundle_version: string;
  model: string;
  latency_ms: number;
  // Optional extras: how many references the citation filter dropped, and the
  // corpus snapshot date shown next to citations.
  citations_removed?: number;
  corpus_date?: string;
}

export interface UsageResponse {
  requests_today: number;
  daily_quota: number;
  requests: number;
  blocked: number;
  refused: number;
}

export interface RuntimeConfig {
  apiBaseUrl: string;
  demoEnabled: boolean;
  riveUrl: string | null;
}

export type StreamEvent =
  | { type: "token"; text: string }
  | { type: "final"; response: AskResponse }
  | { type: "error"; status: number; detail: string; traceId: string | null };

export interface AskHandlers {
  onToken: (text: string) => void;
}

export interface ApiClient {
  ask(question: string, handlers: AskHandlers, signal: AbortSignal): Promise<AskResponse>;
  usage(signal: AbortSignal): Promise<UsageResponse>;
}
