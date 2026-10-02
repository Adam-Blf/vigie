// Access token storage. sessionStorage by default, so closing the tab forgets it;
// localStorage only when the person ticks "stay signed in". Never in a URL.

import { KEYS, readItem, removeItem, writeItem } from "./storage.ts";

export function getToken(): string | null {
  return readItem("session", KEYS.token) ?? readItem("local", KEYS.token);
}

export function isRemembered(): boolean {
  return readItem("local", KEYS.token) !== null;
}

export function saveToken(token: string, remember: boolean): void {
  const value = token.trim();
  clearToken();
  if (!value) return;
  writeItem(remember ? "local" : "session", KEYS.token, value);
}

export function clearToken(): void {
  removeItem("session", KEYS.token);
  removeItem("local", KEYS.token);
}
