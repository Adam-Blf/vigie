// @vitest-environment node
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { expectedMascotFiles } from "../../scripts/export-mascot.ts";
import { mascotFileName, OWL_PALETTES, renderOwlSvg } from "./owl-svg.ts";
import { riveContractProblems } from "./rive-contract.ts";
import { MASCOT_STATES } from "./state.ts";

const staticDir = fileURLToPath(new URL("../../public/mascot/static/", import.meta.url));
const tokens = readFileSync(fileURLToPath(new URL("../styles/tokens.css", import.meta.url)), "utf8");

describe("fallback mascot", () => {
  it("has committed SVGs identical to the generator output", () => {
    const expected = expectedMascotFiles();
    expect(readdirSync(staticDir).sort()).toEqual([...expected.keys()].sort());
    for (const [name, content] of expected) {
      expect(readFileSync(`${staticDir}${name}`, "utf8"), name).toBe(content);
    }
  });

  it("draws seven distinct states on one square viewBox", () => {
    const drawings = MASCOT_STATES.map((state) => renderOwlSvg(state, "light"));
    expect(new Set(drawings).size).toBe(7);
    for (const svg of drawings) expect(svg).toContain('viewBox="0 0 160 160"');
  });

  it("only animates when reduced motion is not requested", () => {
    for (const state of MASCOT_STATES) {
      const svg = renderOwlSvg(state, "dark");
      expect(svg).toContain("@media (prefers-reduced-motion:no-preference)");
      expect(svg.indexOf("@keyframes")).toBeGreaterThan(svg.indexOf("prefers-reduced-motion"));
    }
    expect(renderOwlSvg("idle", "light", { animated: false })).not.toContain("@keyframes");
  });

  it("uses the mascot colours of the design tokens", () => {
    const light = tokens.slice(0, tokens.indexOf("@media"));
    expect(light).toContain(`--color-mascot-body: ${OWL_PALETTES.light.body}`);
    expect(tokens).toContain(`--color-mascot-body: ${OWL_PALETTES.dark.body}`);
  });

  it("names files as the designer contract does", () => {
    expect(mascotFileName("idle", "light")).toBe("vigie-mascot-idle.svg");
    expect(mascotFileName("blocked", "dark")).toBe("vigie-mascot-blocked-dark.svg");
    expect(mascotFileName("poster", "light")).toBe("vigie-mascot-poster.svg");
  });
});

describe("Rive contract", () => {
  it("accepts a file with state, dark and reset of the right kinds", () => {
    expect(
      riveContractProblems([
        { name: "state", kind: "number" },
        { name: "dark", kind: "boolean" },
        { name: "reset", kind: "trigger" },
      ]),
    ).toEqual([]);
  });

  it("lists every missing or mistyped input", () => {
    expect(
      riveContractProblems([
        { name: "state", kind: "boolean" },
        { name: "reset", kind: "trigger" },
      ]),
    ).toEqual(['input "state" is boolean, expected number', 'missing input "dark" (boolean)']);
  });
});
