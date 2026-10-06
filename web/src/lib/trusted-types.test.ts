import { describe, expect, it } from "vitest";
import { installTrustedTypesPolicy, sameOriginScriptUrl } from "./trusted-types.ts";

describe("trusted types policy", () => {
  it("lets same-origin script URLs through and refuses others", () => {
    expect(sameOriginScriptUrl("/sw.js", "https://vigie.example")).toBe("https://vigie.example/sw.js");
    expect(() => sameOriginScriptUrl("https://cdn.example/x.js", "https://vigie.example")).toThrow(/refused/);
    expect(() => sameOriginScriptUrl("//cdn.example/x.js", "https://vigie.example")).toThrow(/refused/);
  });

  it("registers a default policy that refuses HTML when the browser supports it", () => {
    const policies: Record<string, { createHTML?: (html: string) => string }> = {};
    const target = window as unknown as { trustedTypes?: unknown };
    target.trustedTypes = {
      createPolicy: (name: string, rules: { createHTML?: (html: string) => string }) => {
        policies[name] = rules;
        return rules;
      },
    };
    installTrustedTypesPolicy();
    expect(() => policies.default?.createHTML?.("<b>x</b>")).toThrow(/not allowed/);
    delete target.trustedTypes;
    expect(() => installTrustedTypesPolicy()).not.toThrow();
  });
});
