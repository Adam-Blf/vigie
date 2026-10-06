// WCAG 2.2 contrast math and the token pairs Vigie promises to keep readable.
// Pure functions only, so the unit tests and the CLI share the exact same rules.

export type Palette = Record<string, string>;

export interface PairRule {
  fg: string;
  bg: string;
  min: number;
}

export interface PairResult extends PairRule {
  theme: string;
  ratio: number;
  ok: boolean;
}

const TEXT = 4.5;
// Large text, input outlines and focus rings only need 3:1 under WCAG 1.4.11.
const NON_TEXT = 3;

export const PAIRS: readonly PairRule[] = [
  { fg: "text", bg: "surface", min: TEXT },
  { fg: "text", bg: "surface-raised", min: TEXT },
  { fg: "text", bg: "surface-sunken", min: TEXT },
  { fg: "on-surface", bg: "surface", min: TEXT },
  { fg: "on-surface-raised", bg: "surface-raised", min: TEXT },
  { fg: "text-muted", bg: "surface", min: TEXT },
  { fg: "text-muted", bg: "surface-raised", min: TEXT },
  { fg: "text-muted", bg: "surface-sunken", min: TEXT },
  { fg: "primary", bg: "surface", min: TEXT },
  { fg: "primary", bg: "surface-raised", min: TEXT },
  { fg: "danger", bg: "surface-raised", min: TEXT },
  { fg: "warning", bg: "surface-raised", min: TEXT },
  { fg: "success", bg: "surface-raised", min: TEXT },
  { fg: "info", bg: "surface-raised", min: TEXT },
  { fg: "accent", bg: "surface", min: TEXT },
  { fg: "on-primary", bg: "primary", min: TEXT },
  { fg: "on-accent", bg: "accent", min: TEXT },
  { fg: "on-success", bg: "success", min: TEXT },
  { fg: "on-warning", bg: "warning", min: TEXT },
  { fg: "on-danger", bg: "danger", min: TEXT },
  { fg: "on-info", bg: "info", min: TEXT },
  { fg: "citation-fg", bg: "citation-bg", min: TEXT },
  { fg: "border-strong", bg: "surface", min: NON_TEXT },
  { fg: "border-strong", bg: "surface-raised", min: NON_TEXT },
  { fg: "focus", bg: "surface", min: NON_TEXT },
  { fg: "focus", bg: "surface-raised", min: NON_TEXT },
  { fg: "mascot-body", bg: "surface", min: NON_TEXT },
];

// The purple band the brief forbids, in degrees on the HSL wheel.
export const FORBIDDEN_HUE: readonly [number, number] = [250, 310];

export function parseHex(hex: string): [number, number, number] {
  const match = /^#([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match?.[1]) {
    throw new Error(`not a 6-digit hex colour: ${hex}`);
  }
  const value = Number.parseInt(match[1], 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function channel(c: number): number {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

export function luminance(hex: string): number {
  const [r, g, b] = parseHex(hex);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function contrastRatio(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

export function hueAndSaturation(hex: string): { hue: number; saturation: number } {
  const [r, g, b] = parseHex(hex).map((c) => c / 255) as [number, number, number];
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  const lightness = (max + min) / 2;
  if (delta === 0) {
    return { hue: 0, saturation: 0 };
  }
  const saturation = delta / (1 - Math.abs(2 * lightness - 1));
  let hue: number;
  if (max === r) {
    hue = ((g - b) / delta) % 6;
  } else if (max === g) {
    hue = (b - r) / delta + 2;
  } else {
    hue = (r - g) / delta + 4;
  }
  hue *= 60;
  return { hue: hue < 0 ? hue + 360 : hue, saturation };
}

// Pulls `--color-*` hex declarations out of one CSS block body.
export function readColors(block: string): Palette {
  const palette: Palette = {};
  for (const match of block.matchAll(/--color-([a-z-]+):\s*(#[0-9a-f]{6})\s*;/gi)) {
    const [, name, value] = match;
    if (name && value) {
      palette[name] = value.toLowerCase();
    }
  }
  return palette;
}

function blockAfter(css: string, selector: string): string {
  const start = css.indexOf(selector);
  if (start < 0) {
    throw new Error(`selector not found in tokens: ${selector}`);
  }
  const open = css.indexOf("{", start);
  const close = css.indexOf("}", open);
  return css.slice(open + 1, close);
}

export interface Themes {
  light: Palette;
  dark: Palette;
  darkFromMedia: Palette;
}

export function parseThemes(css: string): Themes {
  return {
    light: readColors(blockAfter(css, ":root {")),
    dark: readColors(blockAfter(css, ':root[data-theme="dark"]')),
    darkFromMedia: readColors(blockAfter(css, ':root:not([data-theme="light"])')),
  };
}

export function checkPairs(theme: string, palette: Palette): PairResult[] {
  return PAIRS.map((rule) => {
    const fg = palette[rule.fg];
    const bg = palette[rule.bg];
    if (!fg || !bg) {
      throw new Error(`${theme}: missing token for pair ${rule.fg} on ${rule.bg}`);
    }
    const ratio = contrastRatio(fg, bg);
    return { ...rule, theme, ratio, ok: ratio >= rule.min };
  });
}

// Greys carry no hue worth judging, so only clearly chromatic tokens are checked.
export function forbiddenHues(palette: Palette): string[] {
  const [low, high] = FORBIDDEN_HUE;
  return Object.entries(palette)
    .filter(([, hex]) => {
      const { hue, saturation } = hueAndSaturation(hex);
      return saturation > 0.2 && hue >= low && hue <= high;
    })
    .map(([name]) => name);
}

// The media-query copy of the dark theme must never drift from the toggle copy.
export function darkThemeDrift(themes: Themes): string[] {
  const names = new Set([...Object.keys(themes.dark), ...Object.keys(themes.darkFromMedia)]);
  return [...names].filter((name) => themes.dark[name] !== themes.darkFromMedia[name]);
}
