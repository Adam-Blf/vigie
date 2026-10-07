// EN: post-build step. Reads the packages found in the chunks (plugins/bundled-packages.ts)
// and the Workbox modules inlined in sw.js, then writes the licence notices served with the
// app (MIT and Apache ask for them in every copy) and fails the build on a licence outside
// the allowlist, so a copyleft package cannot ship unnoticed.
// FR : étape après le build. Lit les paquets présents dans les morceaux et les modules
// Workbox intégrés à sw.js, écrit les mentions de licence servies avec l'application (MIT et
// Apache les exigent dans chaque copie) et fait échouer le build sur une licence hors liste.

import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { BUNDLED_PACKAGES_FILE } from "../plugins/bundled-packages.ts";

export const ALLOWED = new Set([
  "MIT",
  "MIT-0",
  "ISC",
  "Apache-2.0",
  "BSD-2-Clause",
  "BSD-3-Clause",
  "0BSD",
  "BlueOak-1.0.0",
  "CC0-1.0",
]);

export interface PackageLicence {
  name: string;
  version: string;
  license: string;
  repository: string;
  text: string | null;
}

// EN: "A OR B" needs one allowed term, "A AND B" needs all of them.
// FR : « A OR B » demande un terme autorisé, « A AND B » les demande tous.
export function isAllowed(expression: string): boolean {
  const clean = expression.replace(/[()]/g, " ").trim();
  if (!clean) return false;
  if (/\sOR\s/.test(clean)) return clean.split(/\s+OR\s+/).some((term) => isAllowed(term));
  return clean.split(/\s+AND\s+/).every((term) => ALLOWED.has(term.trim()));
}

export function workboxModules(serviceWorker: string): string[] {
  const names = new Set<string>();
  for (const match of serviceWorker.matchAll(/workbox:([a-z-]+):\d/g)) {
    if (match[1]) names.add(`workbox-${match[1]}`);
  }
  return [...names].sort();
}

function repositoryOf(meta: Record<string, unknown>): string {
  const repo = meta["repository"];
  if (typeof repo === "string") return repo;
  if (repo && typeof repo === "object" && "url" in repo) return String(repo.url);
  return "";
}

export function readPackage(nodeModules: string, name: string): PackageLicence {
  const dir = join(nodeModules, name);
  const meta = JSON.parse(readFileSync(join(dir, "package.json"), "utf8")) as Record<
    string,
    unknown
  >;
  const file = readdirSync(dir).find((entry) => /^(licen[cs]e|copying)(\.|$)/i.test(entry));
  return {
    name,
    version: String(meta["version"] ?? ""),
    license: String(meta["license"] ?? "UNKNOWN"),
    repository: repositoryOf(meta),
    text: file ? readFileSync(join(dir, file), "utf8").trim() : null,
  };
}

export function renderNotices(packages: readonly PackageLicence[]): string {
  const blocks = packages.map((pkg) => {
    const head = `${pkg.name} ${pkg.version}, licence ${pkg.license}`;
    const source = pkg.repository ? `\nSource : ${pkg.repository}` : "";
    const text =
      pkg.text ?? "Aucun fichier de licence dans le paquet npm, licence déclarée dans package.json.";
    return `${head}${source}\n\n${text}`;
  });
  const intro =
    "Vigie, interface web. Composants tiers inclus dans les fichiers servis, avec leur licence.";
  return `${intro}\n\n${"=".repeat(72)}\n\n${blocks.join(`\n\n${"=".repeat(72)}\n\n`)}\n`;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const dist = fileURLToPath(new URL("../dist/", import.meta.url));
  const nodeModules = fileURLToPath(new URL("../node_modules/", import.meta.url));
  const chunks = JSON.parse(readFileSync(join(dist, BUNDLED_PACKAGES_FILE), "utf8")) as string[];
  const sw = existsSync(join(dist, "sw.js")) ? readFileSync(join(dist, "sw.js"), "utf8") : "";
  const names = [...new Set([...chunks, ...workboxModules(sw)])].sort();
  const packages = names.map((name) => readPackage(nodeModules, name));
  writeFileSync(join(dist, "third-party-licenses.txt"), renderNotices(packages));
  const summary = packages.map(({ name, version, license, repository }) => ({
    name,
    version,
    license,
    repository,
  }));
  writeFileSync(join(dist, "third-party-licenses.json"), `${JSON.stringify(summary, null, 2)}\n`);
  const refused = packages.filter((pkg) => !isAllowed(pkg.license));
  for (const pkg of packages) {
    console.log(`${isAllowed(pkg.license) ? "ok  " : "FAIL"} ${pkg.license.padEnd(14)} ${pkg.name}`);
  }
  process.exitCode = refused.length ? 1 : 0;
}
