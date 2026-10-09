// EN: records which npm packages actually end up in the built chunks. package.json is the
// wrong source: workbox-window is a devDependency and still ships, so the licence notices
// and the licence policy (scripts/third-party-licenses.ts) read this list instead.
// FR : relève les paquets npm réellement présents dans les morceaux construits. Le
// package.json ne suffit pas : workbox-window est en devDependencies et part quand même,
// donc les mentions de licence et la politique de licences lisent cette liste.

import type { Plugin } from "vite";

export const BUNDLED_PACKAGES_FILE = "third-party-packages.json";

// EN: "/node_modules/@scope/name/..." or "/node_modules/name/...", last occurrence wins
// so a nested dependency is credited to itself, not to its parent.
// FR : la dernière occurrence l'emporte, une dépendance imbriquée est créditée à elle-même.
export function packageOf(moduleId: string): string | null {
  // EN: asset names come relative ("node_modules/..."), hence the leading slash.
  // FR : les noms de fichiers arrivent relatifs, d'où la barre ajoutée devant.
  const path = `/${moduleId.replace(/\\/g, "/").replace(/^\0/, "")}`;
  const marker = "/node_modules/";
  const at = path.lastIndexOf(marker);
  if (at < 0) return null;
  const parts = path.slice(at + marker.length).split("/");
  const [first, second] = parts;
  if (!first) return null;
  if (first.startsWith("@")) return second ? `${first}/${second}` : null;
  return first;
}

export function bundledPackages(): Plugin {
  return {
    name: "vigie-bundled-packages",
    apply: "build",
    generateBundle(_options, bundle) {
      const names = new Set<string>();
      for (const output of Object.values(bundle)) {
        // EN: assets count too, a package can ship files referenced from CSS.
        // FR : les fichiers comptent aussi, un paquet peut livrer des fichiers référencés par le CSS.
        const ids = output.type === "chunk" ? output.moduleIds : output.originalFileNames;
        for (const id of ids) {
          const name = packageOf(id);
          if (name) names.add(name);
        }
      }
      this.emitFile({
        type: "asset",
        fileName: BUNDLED_PACKAGES_FILE,
        source: `${JSON.stringify([...names].sort(), null, 2)}\n`,
      });
    },
  };
}
