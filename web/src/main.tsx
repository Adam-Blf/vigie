// Entry point: read the runtime config, pick the real or demo client, then render.

import { render } from "preact";
import { createHttpClient } from "./api/client.ts";
import { App } from "./app/App.tsx";
import { createDemoClient } from "./demo/client.ts";
import { detectLocale, isLocale } from "./i18n/translate.ts";
import { isDemoRequested, loadConfig } from "./lib/config.ts";
import { KEYS, readItem } from "./lib/storage.ts";
import { getToken } from "./lib/token.ts";
import { installTrustedTypesPolicy } from "./lib/trusted-types.ts";
import { watchInstallPrompt } from "./pwa/install.ts";
import "./styles/tokens.css";
import "./styles/icons.css";
import "./styles/base.css";
import "./styles/layout.css";
import "./styles/chat.css";

installTrustedTypesPolicy();
watchInstallPrompt();

async function start(): Promise<void> {
  const config = await loadConfig();
  // Demo mode needs both the ?demo=1 flag and a config that allows it, so production
  // can switch it off without a rebuild.
  const demo = config.demoEnabled && isDemoRequested(window.location.search);
  const client = demo
    ? createDemoClient()
    : createHttpClient({ baseUrl: config.apiBaseUrl, getToken });
  const stored = readItem("local", KEYS.locale);
  const locale = isLocale(stored) ? stored : detectLocale(navigator.languages);
  const root = document.getElementById("app");
  if (!root) throw new Error("missing #app root");
  render(<App config={config} client={client} demo={demo} initialLocale={locale} />, root);
}

void start();
