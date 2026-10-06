import { defineConfig, devices } from "@playwright/test";

// The suite runs against the production build served by `vite preview`, so the service
// worker, the manifest and the real bundle are what gets tested.
const BASE_URL = "http://127.0.0.1:4710";

export default defineConfig({
  testDir: "e2e",
  outputDir: "test-results/e2e",
  fullyParallel: false,
  workers: 2,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: "disabled" },
  },
  use: {
    baseURL: BASE_URL,
    locale: "fr-FR",
    trace: "retain-on-failure",
    // Most tests talk to a mocked API; the service worker would sit between the page and
    // the mock, so it is only enabled in the PWA spec.
    serviceWorkers: "block",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: {
    command: "npx vite build && npx vite preview",
    url: BASE_URL,
    // Never reuse: a stale preview on the port would test an old build without saying so.
    reuseExistingServer: false,
    timeout: 400_000,
  },
});
