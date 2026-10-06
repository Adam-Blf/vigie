// @vitest-environment node
// Repository rules checked mechanically on the web sources: forbidden typography,
// no HTML injection sink, no remote resource in the page.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const WEB = fileURLToPath(new URL("../", import.meta.url));
const SCANNED_DIRS = ["src", "scripts", "plugins", "e2e", "public"];
const TEXT = /\.(ts|tsx|css|html|json|svg|webmanifest|md)$/;

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : TEXT.test(name) ? [path] : [];
  });
}

const files = [
  ...SCANNED_DIRS.map((dir) => join(WEB, dir)).filter(existsSync).flatMap(walk),
  join(WEB, "index.html"),
  join(WEB, "vite.config.ts"),
  join(WEB, "../docs/design/screens.md"),
];

// Built from code points so this file never contains the characters it hunts for.
const FORBIDDEN = new RegExp(`[${String.fromCharCode(0x2014, 0x2013, 0xb7)}]`);
const INVISIBLE = new RegExp(`[${String.fromCharCode(0x200b, 0x200c, 0x200d, 0x2060, 0xfeff, 0x202a, 0x202e)}]`);

describe("web sources", () => {
  it("contain no em dash, en dash or middle dot", () => {
    const offenders = files.filter((file) => FORBIDDEN.test(readFileSync(file, "utf8")));
    expect(offenders).toEqual([]);
  });

  it("contain no invisible or bidirectional control characters", () => {
    const offenders = files.filter((file) => INVISIBLE.test(readFileSync(file, "utf8")));
    expect(offenders).toEqual([]);
  });

  it("never write HTML from strings into the DOM", () => {
    const sinks = /dangerouslySetInnerHTML|\.innerHTML\s*=|outerHTML\s*=|insertAdjacentHTML|document\.write/;
    const offenders = files
      .filter((file) => /src[\\/].*\.tsx?$/.test(file) && !file.endsWith(".test.ts"))
      .filter((file) => sinks.test(readFileSync(file, "utf8")));
    expect(offenders).toEqual([]);
  });

  it("load no resource from another origin in the page shell", () => {
    const html = readFileSync(join(WEB, "index.html"), "utf8");
    expect(html).not.toMatch(/(src|href)="(https?:)?\/\//);
  });
});
