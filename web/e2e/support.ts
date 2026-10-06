// Shared helpers for the end-to-end suite: runtime config, a mocked API that speaks the
// real SSE contract, and a token placed where the app looks for it.

import type { BrowserContext, Page, Route } from "@playwright/test";
import type { AskResponse } from "../src/api/types.ts";
import { DEMO_FIXTURES } from "../src/demo/fixtures.ts";

export function fixture(id: string): AskResponse {
  const found = DEMO_FIXTURES.find((f) => f.id === id);
  if (!found) throw new Error(`no demo fixture ${id}`);
  return structuredClone(found.response);
}

type Target = Page | BrowserContext;

export async function useConfig(target: Target, demoEnabled = false): Promise<void> {
  await target.route("**/config.json", (route) =>
    route.fulfill({ json: { apiBaseUrl: "", demoEnabled, riveUrl: null } }),
  );
}

export async function withToken(target: Target, token = "vig_e2e_token"): Promise<void> {
  await target.addInitScript((value) => window.sessionStorage.setItem("vigie.token", value), token);
}

export function sseBody(response: AskResponse): string {
  const words = response.answer.split(/(?<=\s)/);
  const tokens = words.map((text) => `event: token\ndata: ${JSON.stringify({ text })}\n\n`).join("");
  return `${tokens}event: final\ndata: ${JSON.stringify(response)}\n\n`;
}

export interface AskCall {
  authorization: string | null;
  body: unknown;
  url: string;
}

// Answers /v1/ask with the given payload and records what the page sent.
export async function mockAsk(
  target: Target,
  respond: (route: Route) => Promise<void> | void,
): Promise<AskCall[]> {
  const calls: AskCall[] = [];
  await target.route("**/v1/ask", async (route) => {
    const request = route.request();
    calls.push({
      authorization: request.headers().authorization ?? null,
      body: request.postDataJSON(),
      url: request.url(),
    });
    await respond(route);
  });
  return calls;
}

export function streamOf(response: AskResponse) {
  return (route: Route) =>
    route.fulfill({ status: 200, contentType: "text/event-stream", body: sseBody(response) });
}

export async function ask(page: Page, question: string): Promise<void> {
  await page.locator("#question").fill(question);
  await page.locator("#question").press("Enter");
}
