// Browser storage can throw (private windows, blocked site data, quota), and losing a
// preference must never break the chat. Every read and write goes through here.

export type StoreKind = "session" | "local";

function store(kind: StoreKind): Storage | null {
  try {
    return kind === "session" ? window.sessionStorage : window.localStorage;
  } catch {
    return null;
  }
}

export function readItem(kind: StoreKind, key: string): string | null {
  try {
    return store(kind)?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

export function writeItem(kind: StoreKind, key: string, value: string): void {
  try {
    store(kind)?.setItem(key, value);
  } catch {
    // A full or blocked store only costs persistence, the page keeps working.
  }
}

export function removeItem(kind: StoreKind, key: string): void {
  try {
    store(kind)?.removeItem(key);
  } catch {
    // Same as above: nothing to recover.
  }
}

export const KEYS = {
  token: "vigie.token",
  history: "vigie.history",
  theme: "vigie.theme",
  locale: "vigie.locale",
  questionsAsked: "vigie.questionsAsked",
  installOffered: "vigie.installOffered",
} as const;
