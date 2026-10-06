// Lookup and interpolation, kept free of UI code so it can be tested on its own.

import { en } from "./en.ts";
import { fr, type Dictionary, type MessageKey } from "./fr.ts";

export const LOCALES = ["fr", "en"] as const;
export type Locale = (typeof LOCALES)[number];

export const DICTIONARIES: Record<Locale, Dictionary> = { fr, en };

export type Vars = Record<string, string | number>;

export function translate(locale: Locale, key: MessageKey, vars: Vars = {}): string {
  const template = DICTIONARIES[locale][key];
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => {
    const value = vars[name];
    return value === undefined ? whole : String(value);
  });
}

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

// The browser language only picks English when it clearly asks for it; French stays the default.
export function detectLocale(languages: readonly string[]): Locale {
  const first = languages[0]?.toLowerCase() ?? "fr";
  return first.startsWith("en") ? "en" : "fr";
}
