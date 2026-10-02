// The CSP requires Trusted Types for script sinks. The only sink the app uses is the
// service worker registration, so the default policy lets same-origin script URLs
// through and refuses everything else, HTML included.

interface TrustedTypesFactory {
  createPolicy(
    name: string,
    rules: { createScriptURL?: (url: string) => string; createHTML?: (html: string) => string },
  ): unknown;
}

export function sameOriginScriptUrl(url: string, origin: string): string {
  const parsed = new URL(url, origin);
  if (parsed.origin !== origin) throw new TypeError(`script URL refused: ${parsed.href}`);
  return parsed.href;
}

export function installTrustedTypesPolicy(): void {
  const factory = (window as unknown as { trustedTypes?: TrustedTypesFactory }).trustedTypes;
  if (!factory) return;
  try {
    factory.createPolicy("default", {
      createScriptURL: (url) => sameOriginScriptUrl(url, window.location.origin),
      createHTML: () => {
        throw new TypeError("HTML injection is not allowed in Vigie");
      },
    });
  } catch {
    // A default policy already exists (hot reload in development): keep it.
  }
}
