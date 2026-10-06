// Runtime configuration, fetched from /config.json at start-up. The API base URL is a
// deployment fact, so it is never baked into the bundle at build time.

import type { RuntimeConfig } from "../api/types.ts";

export const DEFAULT_CONFIG: RuntimeConfig = { apiBaseUrl: "", demoEnabled: false, riveUrl: null };

function sameOriginPath(value: unknown): value is string {
  // Only a path on this origin is accepted, so a tampered config cannot point the
  // token at somebody else's server.
  return typeof value === "string" && (value === "" || /^\/(?!\/)/.test(value));
}

export function parseConfig(raw: unknown): RuntimeConfig {
  if (typeof raw !== "object" || raw === null) return DEFAULT_CONFIG;
  const data = raw as Record<string, unknown>;
  return {
    apiBaseUrl: sameOriginPath(data.apiBaseUrl) ? data.apiBaseUrl : DEFAULT_CONFIG.apiBaseUrl,
    demoEnabled: data.demoEnabled === true,
    riveUrl: sameOriginPath(data.riveUrl) && data.riveUrl !== "" ? data.riveUrl : null,
  };
}

export async function loadConfig(fetchImpl: typeof fetch = fetch): Promise<RuntimeConfig> {
  try {
    const response = await fetchImpl("/config.json", { cache: "no-store" });
    if (!response.ok) return DEFAULT_CONFIG;
    return parseConfig(await response.json());
  } catch {
    return DEFAULT_CONFIG;
  }
}

export function isDemoRequested(search: string): boolean {
  return new URLSearchParams(search).get("demo") === "1";
}
