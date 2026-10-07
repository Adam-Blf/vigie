import preact from "@preact/preset-vite";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";
import { bundledPackages } from "./plugins/bundled-packages.ts";
import { mockApi } from "./plugins/mock-api.ts";
import { staticAssets } from "./plugins/static-assets.ts";
import { manifest } from "./plugins/manifest.ts";
import { SECURITY_HEADERS } from "./plugins/security-headers.ts";
import packageJson from "./package.json" with { type: "json" };

// Port 4710 is the one reserved for the Vigie web app; bound to loopback only.
// VIGIE_WEB_PORT moves it when another local stack already holds 4710.
const server = { host: "127.0.0.1", port: Number(process.env.VIGIE_WEB_PORT ?? 4710), strictPort: true };

// Only a loopback API is accepted: the proxy forwards the visitor's token, and a typo in
// the variable must not send it to another host.
function apiProxy(target: string | undefined): Record<string, string> {
  if (!target) return {};
  const { hostname } = new URL(target);
  if (hostname !== "127.0.0.1" && hostname !== "localhost") {
    throw new Error(`VIGIE_API_PROXY must be a loopback URL, got ${hostname}`);
  }
  return { "/v1": target };
}

export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(packageJson.version) },
  server,
  // The dev server needs inline HMR code, so the strict policy applies to preview only.
  // VIGIE_API_PROXY points preview at a running API (the live e2e suite), so the page and
  // /v1 share one origin as behind nginx in production and the CSP stays at 'self'.
  preview: { ...server, headers: SECURITY_HEADERS, proxy: apiProxy(process.env.VIGIE_API_PROXY) },
  build: {
    target: "es2022",
    sourcemap: false,
  },
  plugins: [
    preact(),
    staticAssets(),
    bundledPackages(),
    mockApi(),
    VitePWA({
      registerType: "prompt",
      injectRegister: null,
      manifest,
      includeAssets: ["favicon.svg", "icons/*.png", "mascot/static/*.svg"],
      workbox: {
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/v1\//],
        globPatterns: ["**/*.{js,css,html,svg,png,woff2,webmanifest}"],
        // The Rive runtime is only fetched when a .riv file is configured.
        globIgnores: ["vendor/**", "**/rive-*.js"],
        cleanupOutdatedCaches: true,
        // One self-contained worker: importScripts() is a Trusted Types sink under our CSP.
        inlineWorkboxRuntime: true,
        runtimeCaching: [
          {
            // Anything carrying a token is personal: never stored, whatever its path.
            urlPattern: ({ request }) => request.headers.has("authorization"),
            handler: "NetworkOnly",
          },
          {
            // API answers may be sensitive, so /v1/* never touches the cache.
            urlPattern: ({ url }) => url.pathname.startsWith("/v1/"),
            handler: "NetworkOnly",
          },
          {
            urlPattern: ({ url }) => url.pathname === "/config.json",
            handler: "NetworkFirst",
            options: { cacheName: "vigie-config", networkTimeoutSeconds: 3 },
          },
        ],
      },
    }),
  ],
  test: {
    environment: "jsdom",
    // Few workers: jsdom start-up is heavy and parallel agents share this machine.
    maxWorkers: 2,
    include: ["src/**/*.test.ts", "scripts/**/*.test.ts"],
    coverage: { provider: "v8", include: ["src/**/*.ts"], exclude: ["src/**/*.test.ts"] },
  },
});
