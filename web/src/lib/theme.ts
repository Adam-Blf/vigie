// Theme choice: follow the system, or force light or dark. The choice is written on
// <html data-theme> so tokens.css can switch palettes without any component knowing.

import { KEYS, readItem, removeItem, writeItem } from "./storage.ts";

export const THEME_CHOICES = ["system", "light", "dark"] as const;
export type ThemeChoice = (typeof THEME_CHOICES)[number];
export type EffectiveTheme = "light" | "dark";

// Kept equal to --color-surface in tokens.css, which the contrast script checks.
const THEME_COLORS: Record<EffectiveTheme, string> = { light: "#f6f8f8", dark: "#0d1719" };

export function readThemeChoice(): ThemeChoice {
  const stored = readItem("local", KEYS.theme);
  return stored === "light" || stored === "dark" ? stored : "system";
}

export function systemTheme(): EffectiveTheme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function effectiveTheme(choice: ThemeChoice): EffectiveTheme {
  return choice === "system" ? systemTheme() : choice;
}

export function nextThemeChoice(choice: ThemeChoice): ThemeChoice {
  const index = THEME_CHOICES.indexOf(choice);
  return THEME_CHOICES[(index + 1) % THEME_CHOICES.length] ?? "system";
}

export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") {
    delete root.dataset.theme;
    removeItem("local", KEYS.theme);
  } else {
    root.dataset.theme = choice;
    writeItem("local", KEYS.theme, choice);
  }
  // Two theme-color metas follow the system; a forced theme pins both to its colour.
  for (const meta of document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
    const media = meta.dataset.scheme === "dark" ? "dark" : "light";
    meta.content = THEME_COLORS[choice === "system" ? media : choice];
  }
}
