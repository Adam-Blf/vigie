// Proof of "no CDN": every request the app makes, on every screen and through a full
// question, stays on the app's own origin.

import { expect, test } from "@playwright/test";
import { ask, fixture, mockAsk, streamOf, useConfig, withToken } from "./support.ts";

test.use({ serviceWorkers: "allow" });

test("no request ever leaves the app origin", async ({ page, context, baseURL }) => {
  const origin = new URL(baseURL ?? "").origin;
  const foreign: string[] = [];
  context.on("request", (request) => {
    const url = new URL(request.url());
    if (url.protocol === "data:" || url.protocol === "blob:") return;
    if (url.origin !== origin) foreign.push(request.url());
  });
  await useConfig(context);
  await withToken(context);
  await mockAsk(context, streamOf(fixture("gdpr-breach")));

  for (const path of ["/", "/settings", "/usage", "/about", "/legal", "/privacy", "/nope"]) {
    await page.goto(path);
    await expect(page.locator("main h1")).toBeVisible();
  }
  await page.goto("/");
  await ask(page, "Délai de notification ?");
  await expect(page.locator(".bubble-answer")).toContainText("72 heures");
  await page.locator(".citation-chip").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.waitForLoadState("networkidle");

  expect(foreign).toEqual([]);
});
