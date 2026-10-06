// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { buildIconsCss, ICONS_CSS, phosphorRegularCss } from "./build-icons.ts";
import { initialScripts } from "./check-bundle.ts";

describe("generated icon stylesheet", () => {
  it("is in sync with the icon list", () => {
    expect(readFileSync(ICONS_CSS, "utf8")).toBe(buildIconsCss(phosphorRegularCss()));
  });

  it("fails loudly on an icon Phosphor does not have", () => {
    expect(() => buildIconsCss(".ph.ph-x:before { content: \"x\"; }")).toThrow(/no icon named/);
  });
});

describe("bundle budget", () => {
  it("counts the entry script and its preloads, once each", () => {
    const html =
      '<script src="/theme-init.js"></script><script type="module" crossorigin src="/assets/index-a.js"></script>' +
      '<link rel="modulepreload" crossorigin href="/assets/vendor-b.js"><link rel="stylesheet" href="/x.css">';
    expect(initialScripts(html)).toEqual(["/theme-init.js", "/assets/index-a.js", "/assets/vendor-b.js"]);
  });
});
