// Service worker, installability and offline behaviour, against the production build.

import { expect, test } from "@playwright/test";
import { ask, fixture, mockAsk, streamOf, useConfig, withToken } from "./support.ts";

test.use({ serviceWorkers: "allow" });

test("the manifest is complete and Chrome reports no installability error", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => navigator.serviceWorker.ready);
  const manifest = await page.evaluate(() => fetch("/manifest.webmanifest").then((r) => r.json()));
  expect(manifest).toMatchObject({
    name: "Vigie",
    short_name: "Vigie",
    display: "standalone",
    start_url: "/",
    scope: "/",
  });
  expect(manifest.theme_color).toMatch(/^#/);
  expect(manifest.background_color).toMatch(/^#/);
  const icons = manifest.icons as { sizes: string; purpose: string }[];
  expect(icons.map((i) => `${i.sizes} ${i.purpose}`)).toEqual([
    "192x192 any",
    "512x512 any",
    "512x512 maskable",
  ]);

  const session = await page.context().newCDPSession(page);
  const { installabilityErrors } = await session.send("Page.getInstallabilityErrors");
  expect(installabilityErrors).toEqual([]);
});

test("the app shell works offline and shows the offline owl", async ({ page, context }) => {
  await useConfig(context);
  await page.goto("/");
  await page.evaluate(() => navigator.serviceWorker.ready);
  // A second load makes the page controlled by the now-active worker.
  await page.reload();
  await expect.poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null)).toBe(true);

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Vous êtes hors ligne" })).toBeVisible();
  await expect(page.locator(".status-screen .mascot")).toHaveAttribute("data-state", "error");
  await expect(page.locator(".status-screen img")).toHaveAttribute("src", /vigie-mascot-error/);
  await context.setOffline(false);
});

test("API answers never reach a cache, and requests with a token are never stored", async ({ page, context }) => {
  await useConfig(context);
  await withToken(context);
  await mockAsk(context, streamOf(fixture("gdpr-breach")));
  await page.goto("/");
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  await expect.poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null)).toBe(true);
  await ask(page, "Délai de notification ?");
  await expect(page.locator(".bubble-answer")).toContainText("72 heures");

  const cached = await page.evaluate(async () => {
    const urls: string[] = [];
    for (const name of await caches.keys()) {
      const cache = await caches.open(name);
      for (const request of await cache.keys()) urls.push(request.url);
    }
    return urls;
  });
  expect(cached.length).toBeGreaterThan(5);
  expect(cached.filter((url) => new URL(url).pathname.startsWith("/v1/"))).toEqual([]);
});
