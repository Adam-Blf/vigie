import preact from "@preact/preset-vite";
import { defineConfig } from "vitest/config";

// Port 4710 is the one reserved for the Vigie web app; bound to loopback only.
const server = { host: "127.0.0.1", port: 4710, strictPort: true };

export default defineConfig({
  server,
  preview: server,
  plugins: [preact()],
  test: {
    environment: "jsdom",
    // Few workers: jsdom start-up is heavy and parallel agents share this machine.
    maxWorkers: 2,
    include: ["src/**/*.test.ts", "scripts/**/*.test.ts"],
    coverage: { provider: "v8", include: ["src/**/*.ts"], exclude: ["src/**/*.test.ts"] },
  },
});
