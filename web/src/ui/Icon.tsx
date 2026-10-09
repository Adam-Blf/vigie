import { h, type ComponentChild } from "preact";
import { ICONS, type IconName } from "./icon-names.ts";

// The CSP requires Trusted Types and the app refuses every HTML sink, so the markup that
// ships inside each Reicon glyph (a handful of SVG shapes) is turned into Preact nodes
// instead of being injected with innerHTML.

const TOKEN = /<(\/)?([a-zA-Z]+)((?:\s+[a-zA-Z-]+="[^"]*")*)\s*(\/)?>/g;
const ATTRIBUTE = /([a-zA-Z-]+)="([^"]*)"/g;

export function parseGlyph(markup: string): ComponentChild[] {
  const root: ComponentChild[] = [];
  const stack: { tag: string; props: Record<string, string>; children: ComponentChild[] }[] = [];
  const append = (node: ComponentChild) => (stack.at(-1)?.children ?? root).push(node);
  let consumed = 0;
  for (const match of markup.matchAll(TOKEN)) {
    if (markup.slice(consumed, match.index).trim() !== "") throw new Error("unexpected text in icon");
    consumed = match.index + match[0].length;
    const [, closing, tag = "", attributes = "", selfClosing] = match;
    if (closing) {
      const open = stack.pop();
      if (!open || open.tag !== tag) throw new Error(`unbalanced </${tag}> in icon`);
      append(h(open.tag, open.props, ...open.children));
      continue;
    }
    const props: Record<string, string> = {};
    for (const attribute of attributes.matchAll(ATTRIBUTE)) {
      if (attribute[1] && attribute[2] !== undefined) props[attribute[1]] = attribute[2];
    }
    if (selfClosing) append(h(tag, props));
    else stack.push({ tag, props, children: [] });
  }
  if (stack.length > 0 || markup.slice(consumed).trim() !== "") throw new Error("malformed icon");
  return root;
}

const GLYPHS = new Map<IconName, ComponentChild[]>();

function glyphOf(name: IconName): ComponentChild[] {
  let nodes = GLYPHS.get(name);
  if (!nodes) {
    nodes = parseGlyph(ICONS[name].iconData.O ?? "");
    GLYPHS.set(name, nodes);
  }
  return nodes;
}

// Icons are always decorative here: the button or text next to them carries the meaning.
export function Icon({ name }: { name: IconName }) {
  return (
    <svg class="reicon" width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {glyphOf(name)}
    </svg>
  );
}
