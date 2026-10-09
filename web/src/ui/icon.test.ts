import { describe, expect, it } from "vitest";
import { parseGlyph } from "./Icon.tsx";
import { ICONS, LOCAL_ICONS } from "./icon-names.ts";

describe("Reicon glyphs", () => {
  it("parses every glyph the interface uses into at least one node", () => {
    for (const name of Object.keys(ICONS) as (keyof typeof ICONS)[]) {
      expect(parseGlyph(ICONS[name].iconData.O ?? "").length, name).toBeGreaterThan(0);
    }
    for (const markup of Object.values(LOCAL_ICONS)) expect(parseGlyph(markup).length).toBeGreaterThan(0);
  });

  it("keeps the attributes and the nesting of a clipped glyph", () => {
    const [group] = parseGlyph('<g clip-path="url(#a)"><path d="M0 0" fill="currentColor"/></g>');
    expect(group).toMatchObject({ type: "g", props: { "clip-path": "url(#a)" } });
  });

  it("refuses text and unbalanced markup instead of rendering it", () => {
    expect(() => parseGlyph("<path d='x'/>")).toThrow();
    expect(() => parseGlyph('<g><path d="x"/>')).toThrow(/malformed/);
    expect(() => parseGlyph('hello<path d="x"/>')).toThrow(/text/);
  });
});
