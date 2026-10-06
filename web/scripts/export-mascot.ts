// Writes the fallback mascot SVGs (7 states plus a poster, light and dark) into
// public/mascot/static. Run after any change to src/mascot/owl-svg.ts.

import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { mascotFileName, renderOwlSvg, type MascotTheme } from "../src/mascot/owl-svg.ts";
import { MASCOT_STATES } from "../src/mascot/state.ts";

export function expectedMascotFiles(): Map<string, string> {
  const files = new Map<string, string>();
  for (const theme of ["light", "dark"] as const satisfies readonly MascotTheme[]) {
    for (const state of MASCOT_STATES) {
      files.set(mascotFileName(state, theme), `${renderOwlSvg(state, theme)}\n`);
    }
    files.set(mascotFileName("poster", theme), `${renderOwlSvg("idle", theme, { animated: false })}\n`);
  }
  return files;
}

export const MASCOT_DIR = fileURLToPath(new URL("../public/mascot/static/", import.meta.url));

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  mkdirSync(MASCOT_DIR, { recursive: true });
  for (const [name, content] of expectedMascotFiles()) {
    writeFileSync(`${MASCOT_DIR}${name}`, content, "utf8");
  }
  console.log(`mascot: wrote ${expectedMascotFiles().size} files to public/mascot/static`);
}
