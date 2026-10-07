import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { packageOf } from "../plugins/bundled-packages.ts";
import { isAllowed, readPackage, renderNotices, workboxModules } from "./third-party-licenses.ts";

describe("packageOf", () => {
  it("names plain, scoped and nested packages", () => {
    expect(packageOf("/w/node_modules/preact/dist/preact.mjs")).toBe("preact");
    expect(packageOf("C:\\w\\node_modules\\@rive-app\\canvas\\rive.js")).toBe("@rive-app/canvas");
    expect(packageOf("/w/node_modules/a/node_modules/b/index.js")).toBe("b");
    expect(packageOf("\0/w/node_modules/preact/hooks/dist/hooks.mjs")).toBe("preact");
  });

  it("ignores the app's own modules", () => {
    expect(packageOf("/w/src/main.tsx")).toBeNull();
    expect(packageOf("/w/node_modules/@scope")).toBeNull();
  });
});

describe("isAllowed", () => {
  it("accepts permissive licences and expressions", () => {
    expect(isAllowed("MIT")).toBe(true);
    expect(isAllowed("(MIT OR CC0-1.0)")).toBe(true);
    expect(isAllowed("Apache-2.0 AND MIT")).toBe(true);
  });

  it("refuses copyleft, unknown and mixed expressions", () => {
    expect(isAllowed("GPL-3.0-only")).toBe(false);
    expect(isAllowed("AGPL-3.0-or-later")).toBe(false);
    expect(isAllowed("MIT AND GPL-2.0-only")).toBe(false);
    expect(isAllowed("UNKNOWN")).toBe(false);
    expect(isAllowed("")).toBe(false);
  });
});

describe("notices", () => {
  it("finds the Workbox modules inlined in the service worker", () => {
    const sw = 'self["workbox:core:7.4.0"]&&x;self["workbox:routing:7.4.0"];"workbox:core:7.4.0"';
    expect(workboxModules(sw)).toEqual(["workbox-core", "workbox-routing"]);
  });

  it("reads the licence file and renders it", () => {
    const root = mkdtempSync(join(tmpdir(), "vigie-lic-"));
    mkdirSync(join(root, "demo"));
    writeFileSync(
      join(root, "demo", "package.json"),
      JSON.stringify({ version: "1.2.3", license: "MIT", repository: { url: "git+https://x/demo" } }),
    );
    writeFileSync(join(root, "demo", "LICENSE.md"), "Copyright (c) Demo\n");
    const pkg = readPackage(root, "demo");
    expect(pkg).toMatchObject({ version: "1.2.3", license: "MIT", text: "Copyright (c) Demo" });
    const text = renderNotices([pkg, { ...pkg, name: "bare", text: null, repository: "" }]);
    expect(text).toContain("demo 1.2.3, licence MIT\nSource : git+https://x/demo");
    expect(text).toContain("Copyright (c) Demo");
    expect(text).toContain("Aucun fichier de licence");
  });
});
