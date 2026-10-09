// @vitest-environment node
import { describe, expect, it } from "vitest";
import { initialScripts } from "./check-bundle.ts";

describe("bundle budget", () => {
  it("counts the entry script and its preloads, once each", () => {
    const html =
      '<script src="/theme-init.js"></script><script type="module" crossorigin src="/assets/index-a.js"></script>' +
      '<link rel="modulepreload" crossorigin href="/assets/vendor-b.js"><link rel="stylesheet" href="/x.css">';
    expect(initialScripts(html)).toEqual(["/theme-init.js", "/assets/index-a.js", "/assets/vendor-b.js"]);
  });
});
