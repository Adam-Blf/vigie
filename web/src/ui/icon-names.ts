// The Phosphor icons the interface uses, regular weight only. scripts/build-icons.ts
// turns this list into src/styles/icons.css, so the page ships a few dozen rules
// instead of the 1 500 of the full stylesheet.

export const ICON_NAMES = [
  "arrow-clockwise",
  "arrow-square-out",
  "book-open",
  "chart-bar",
  "chat-circle-text",
  "check",
  "circle-half",
  "copy",
  "download-simple",
  "gear",
  "info",
  "moon",
  "note-pencil",
  "paper-plane-right",
  "shield-warning",
  "sign-out",
  "stop",
  "sun",
  "trash",
  "warning",
  "wifi-slash",
  "x",
] as const;

export type IconName = (typeof ICON_NAMES)[number];
