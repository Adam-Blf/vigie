// Web app manifest. Colours match --color-surface (background) and the light theme so
// the splash screen and the first paint agree.

import type { ManifestOptions } from "vite-plugin-pwa";

export const manifest: Partial<ManifestOptions> = {
  id: "/",
  name: "Vigie",
  short_name: "Vigie",
  description:
    "Copilote conformité qui répond sur DORA, l'AI Act, le RGPD et l'AMLR en citant l'article exact.",
  lang: "fr",
  dir: "ltr",
  start_url: "/",
  scope: "/",
  display: "standalone",
  orientation: "any",
  theme_color: "#f6f8f8",
  background_color: "#f6f8f8",
  categories: ["business", "productivity"],
  icons: [
    { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
    { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    {
      src: "/icons/icon-512-maskable.png",
      sizes: "512x512",
      type: "image/png",
      purpose: "maskable",
    },
  ],
};
