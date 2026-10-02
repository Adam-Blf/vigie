// Budget gate from brief 11.3: the JavaScript loaded by the first page view must stay
// under 120 KB gzip. Counts the entry script and every module it preloads.

import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";

export const INITIAL_JS_BUDGET_BYTES = 120 * 1024;

export function initialScripts(html: string): string[] {
  const sources = new Set<string>();
  for (const match of html.matchAll(/<script[^>]*\bsrc="([^"]+\.js)"/g)) {
    if (match[1]) sources.add(match[1]);
  }
  for (const match of html.matchAll(/<link[^>]*rel="modulepreload"[^>]*href="([^"]+\.js)"/g)) {
    if (match[1]) sources.add(match[1]);
  }
  return [...sources];
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const dist = fileURLToPath(new URL("../dist/", import.meta.url));
  const html = readFileSync(`${dist}index.html`, "utf8");
  let total = 0;
  for (const src of initialScripts(html)) {
    const size = gzipSync(readFileSync(`${dist}${src.replace(/^\//, "")}`)).length;
    total += size;
    console.log(`${(size / 1024).toFixed(1).padStart(7)} KB gzip  ${src}`);
  }
  const ok = total <= INITIAL_JS_BUDGET_BYTES;
  console.log(
    `${ok ? "ok" : "FAIL"} initial JS ${(total / 1024).toFixed(1)} KB gzip ` +
      `(budget ${INITIAL_JS_BUDGET_BYTES / 1024} KB)`,
  );
  process.exitCode = ok ? 0 : 1;
}
