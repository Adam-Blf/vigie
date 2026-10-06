import { defineConfig, devices } from "@playwright/test";

// Live suite: the production build talks to a real Vigie API started beforehand, through
// the preview proxy, so the page and /v1 share one origin like behind nginx. Nothing is
// mocked here. Needs VIGIE_API_PROXY (loopback URL of the API) and VIGIE_E2E_TOKEN.
const BASE_URL = `http://127.0.0.1:${process.env.VIGIE_WEB_PORT ?? 4710}`;

if (!process.env.VIGIE_API_PROXY || !process.env.VIGIE_E2E_TOKEN) {
  throw new Error("the live suite needs VIGIE_API_PROXY and VIGIE_E2E_TOKEN");
}

export default defineConfig({
  testDir: "e2e-live",
  outputDir: "test-results/e2e-live",
  fullyParallel: false,
  // One worker: the API under test runs on the same machine as the browser.
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    locale: "fr-FR",
    trace: "retain-on-failure",
    serviceWorkers: "block",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: {
    command: "npx vite build && npx vite preview",
    url: BASE_URL,
    reuseExistingServer: false,
    timeout: 400_000,
  },
});
