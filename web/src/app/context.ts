// Shared application state handed down through one context: language, theme, the API
// client in use (real or demo) and what the last answer told us about the server.

import { createContext } from "preact";
import { useContext } from "preact/hooks";
import type { ApiClient, AskResponse, RuntimeConfig } from "../api/types.ts";
import type { MessageKey } from "../i18n/fr.ts";
import type { Locale, Vars } from "../i18n/translate.ts";
import type { ThemeChoice } from "../lib/theme.ts";

export interface ServerInfo {
  appVersion: string;
  model: string;
}

export interface AppState {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, vars?: Vars) => string;
  theme: ThemeChoice;
  setTheme: (theme: ThemeChoice) => void;
  client: ApiClient;
  config: RuntimeConfig;
  demo: boolean;
  online: boolean;
  server: ServerInfo | null;
  noteAnswer: (response: AskResponse) => void;
}

export const AppContext = createContext<AppState | null>(null);

export function useApp(): AppState {
  const state = useContext(AppContext);
  if (!state) throw new Error("useApp must be used inside AppContext");
  return state;
}
