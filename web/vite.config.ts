import preact from "@preact/preset-vite";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";
import { mockApi } from "./plugins/mock-api.ts";
import { staticAssets } from "./plugins/static-assets.ts";
import { manifest } from "./plugins/manifest.ts";
import packageJson from "./package.json" with { type: "json" };

// Port 4710 is the one reserved for the Vigie web app; bound to loopback only.
const server = { host: "127.0.0.1", port: 4710, strictPort: true };

export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(packageJson.version) },
  server,
  preview: server,
  build: {
    target: "es2022",
    sourcemap: false,
  },
  plugins: [
    preact(),
    staticAssets(),
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
