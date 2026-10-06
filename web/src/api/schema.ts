// Runtime guards for what the server sends. TypeScript types vanish at runtime, and
// a malformed payload must become a readable error, not a blank bubble.

import { BLOCK_REASONS, type AskResponse, type Citation, type UsageResponse } from "./types.ts";

type Json = Record<string, unknown>;

function isObject(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const isString = (v: unknown): v is string => typeof v === "string";
const isNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export function isCitation(value: unknown): value is Citation {
  return (
    isObject(value) &&
    isString(value.label) &&
    isString(value.regulation) &&
    isString(value.article) &&
    (value.paragraph === null || isString(value.paragraph)) &&
    isString(value.excerpt) &&
    isString(value.url) &&
    // Only official EUR-Lex links may become anchors in the page.
    value.url.startsWith("https://eur-lex.europa.eu/")
  );
}

export function isAskResponse(value: unknown): value is AskResponse {
  if (!isObject(value)) return false;
  const reason = value.block_reason;
  return (
    isString(value.answer) &&
    Array.isArray(value.citations) &&
    value.citations.every(isCitation) &&
    typeof value.blocked === "boolean" &&
    (reason === null || (isString(reason) && (BLOCK_REASONS as readonly string[]).includes(reason))) &&
    typeof value.refused === "boolean" &&
    isString(value.trace_id) &&
    isString(value.app_version) &&
    isString(value.bundle_version) &&
    isString(value.model) &&
    isNumber(value.latency_ms) &&
    (value.citations_removed === undefined || isNumber(value.citations_removed)) &&
    (value.corpus_date === undefined || isString(value.corpus_date))
  );
}

export function isUsageResponse(value: unknown): value is UsageResponse {
  return (
    isObject(value) &&
    isNumber(value.questions_today) &&
    isNumber(value.daily_quota) &&
    isNumber(value.questions_total) &&
    (value.last_used_at === null || isString(value.last_used_at))
  );
}
