// Two files the page needs outside the module graph, built from sources in the repo:
// - theme-init.js, compiled from src/boot/theme-init.ts, loaded as a classic blocking
//   script so the theme is set before the first paint (an inline script would break CSP);
// - vendor/rive.wasm, copied from node_modules so the Rive runtime never hits a CDN.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { transformWithOxc, type Plugin } from "vite";

const THEME_INIT_SOURCE = fileURLToPath(new URL("../src/boot/theme-init.ts", import.meta.url));
export const RIVE_WASM_PATH = "vendor/rive.wasm";

function riveWasmFile(): string {
  const require = createRequire(import.meta.url);
  return require.resolve("@rive-app/canvas/rive.wasm");
}

async function compileThemeInit(): Promise<string> {
  const source = readFileSync(THEME_INIT_SOURCE, "utf8");
  const result = await transformWithOxc(source, THEME_INIT_SOURCE, {
    lang: "ts",
    target: "es2020",
  });
  return result.code;
}

export function staticAssets(): Plugin {
  return {
    name: "vigie-static-assets",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url === "/theme-init.js") {
          compileThemeInit().then(
            (code) => {
              res.setHeader("Content-Type", "text/javascript");
              res.end(code);
            },
            (error: unknown) => next(error),
          );
          return;
        }
        if (req.url === `/${RIVE_WASM_PATH}`) {
          res.setHeader("Content-Type", "application/wasm");
          res.end(readFileSync(riveWasmFile()));
          return;
        }
        next();
      });
    },
    async generateBundle() {
      this.emitFile({ type: "asset", fileName: "theme-init.js", source: await compileThemeInit() });
      this.emitFile({ type: "asset", fileName: RIVE_WASM_PATH, source: readFileSync(riveWasmFile()) });
    },
  };
}
