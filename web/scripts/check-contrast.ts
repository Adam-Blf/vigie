// CLI gate: exits non-zero when a token pair falls under its WCAG minimum, when a
// chromatic token sits in the forbidden purple band, or when the two dark copies drift.
// Usage: node scripts/check-contrast.ts [path/to/tokens.css]

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { checkPairs, darkThemeDrift, forbiddenHues, parseThemes } from "./contrast-lib.ts";

const defaultPath = fileURLToPath(new URL("../src/styles/tokens.css", import.meta.url));
const path = process.argv[2] ?? defaultPath;
const themes = parseThemes(readFileSync(path, "utf8"));

let failures = 0;
for (const [name, palette] of [
  ["light", themes.light],
  ["dark", themes.dark],
] as const) {
  for (const result of checkPairs(name, palette)) {
    const mark = result.ok ? "ok  " : "FAIL";
    console.log(
      `${mark} ${name.padEnd(5)} ${result.fg.padEnd(18)} on ${result.bg.padEnd(15)} ` +
        `${result.ratio.toFixed(2)}:1 (min ${result.min}:1)`,
    );
    if (!result.ok) failures += 1;
  }
  for (const token of forbiddenHues(palette)) {
    console.log(`FAIL ${name} ${token} uses a hue between 250 and 310 degrees`);
    failures += 1;
  }
}
for (const token of darkThemeDrift(themes)) {
  console.log(`FAIL dark ${token} differs between the media query and data-theme copies`);
  failures += 1;
}

console.log(failures === 0 ? "contrast: all pairs pass" : `contrast: ${failures} failure(s)`);
process.exitCode = failures === 0 ? 0 : 1;
