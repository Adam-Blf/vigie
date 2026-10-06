// Fallback app icons (favicon, PWA icons, Apple touch icon), drawn from the same owl as
// the mascot and rasterised with Playwright's Chromium, which the e2e suite already needs.
// The designer's lot 1 replaces every file this writes.

import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { renderOwlSvg } from "../src/mascot/owl-svg.ts";

const BRAND = "#0b5c6b";
const PUBLIC = fileURLToPath(new URL("../public/", import.meta.url));

// `scale` is the share of the square the owl may cover. Maskable icons keep the motif
// inside the central safe zone, since launchers crop up to a circle.
export function renderIconSvg(scale: number, rounded: boolean): string {
  const size = 512;
  const owl = size * scale;
  const offset = (size - owl) / 2;
  const nested = renderOwlSvg("idle", "dark", { animated: false }).replace(
    'width="160" height="160"',
    `x="${offset}" y="${offset + owl * 0.02}" width="${owl}" height="${owl}"`,
  );
  const radius = rounded ? 112 : 0;
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}">` +
    `<rect width="${size}" height="${size}" rx="${radius}" fill="${BRAND}"/>${nested}</svg>`
  );
}

const RASTERS: readonly { file: string; size: number; scale: number; rounded: boolean }[] = [
  { file: "icons/icon-192.png", size: 192, scale: 0.78, rounded: false },
  { file: "icons/icon-512.png", size: 512, scale: 0.78, rounded: false },
  { file: "icons/icon-512-maskable.png", size: 512, scale: 0.56, rounded: false },
  { file: "icons/apple-touch-icon-180.png", size: 180, scale: 0.72, rounded: false },
  { file: "icons/favicon-16.png", size: 16, scale: 0.92, rounded: true },
  { file: "icons/favicon-32.png", size: 32, scale: 0.92, rounded: true },
  { file: "icons/favicon-48.png", size: 48, scale: 0.9, rounded: true },
];

async function main(): Promise<void> {
  mkdirSync(`${PUBLIC}icons`, { recursive: true });
  writeFileSync(`${PUBLIC}favicon.svg`, `${renderIconSvg(0.92, true)}\n`, "utf8");
  const browser = await chromium.launch();
  try {
    for (const raster of RASTERS) {
      const page = await browser.newPage({
        viewport: { width: raster.size, height: raster.size },
      });
      const svg = renderIconSvg(raster.scale, raster.rounded).replace(
        "<svg ",
        `<svg width="${raster.size}" height="${raster.size}" `,
      );
      await page.setContent(
        `<html><body style="margin:0;background:transparent">${svg}</body></html>`,
      );
      writeFileSync(
        `${PUBLIC}${raster.file}`,
        await page.screenshot({ omitBackground: true, type: "png" }),
      );
      await page.close();
    }
  } finally {
    await browser.close();
  }
  console.log(`icons: wrote favicon.svg and ${RASTERS.length} PNG files`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  await main();
}
