// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  checkPairs,
  contrastRatio,
  darkThemeDrift,
  forbiddenHues,
  hueAndSaturation,
  parseHex,
  parseThemes,
} from "./contrast-lib.ts";

const tokensPath = fileURLToPath(new URL("../src/styles/tokens.css", import.meta.url));
const tokens = readFileSync(tokensPath, "utf8");

describe("contrast gate", () => {
  it("computes WCAG ratios", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(contrastRatio("#777777", "#ffffff")).toBeCloseTo(4.48, 2);
    expect(() => parseHex("#fff")).toThrow();
  });

  it("passes on the shipped tokens, in both themes", () => {
    const themes = parseThemes(tokens);
    for (const [name, palette] of [
      ["light", themes.light],
      ["dark", themes.dark],
    ] as const) {
      const failing = checkPairs(name, palette).filter((r) => !r.ok);
      expect(failing).toEqual([]);
      expect(forbiddenHues(palette)).toEqual([]);
    }
    expect(darkThemeDrift(themes)).toEqual([]);
  });

  it("goes red on a degraded palette (gate seen failing)", () => {
    const degraded = tokens.replace("--color-text-muted: #4a5d63;", "--color-text-muted: #9aa5a8;");
    const failing = checkPairs("light", parseThemes(degraded).light).filter((r) => !r.ok);
    expect(failing.map((r) => `${r.fg}/${r.bg}`)).toContain("text-muted/surface");
  });

  it("flags purple hues and dark theme drift", () => {
    expect(hueAndSaturation("#7c3aed").hue).toBeGreaterThan(250);
    expect(forbiddenHues({ primary: "#7c3aed", grey: "#777777" })).toEqual(["primary"]);
    const drifted = tokens.replace(
      ':root[data-theme="dark"] {\n  --color-surface: #0d1719;',
      ':root[data-theme="dark"] {\n  --color-surface: #0d1718;',
    );
    expect(darkThemeDrift(parseThemes(drifted))).toEqual(["surface"]);
  });

  it("refuses a palette that lost a token", () => {
    expect(() => checkPairs("light", { text: "#000000" })).toThrow(/missing token/);
  });
});
