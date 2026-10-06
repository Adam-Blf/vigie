// Development-only mock of the Vigie API, mounted on the Vite dev server. It speaks the
// same contract as the real API (SSE on /v1/ask, JSON on /v1/usage/me) from the demo
// fixtures, so the interface can be built before the backend exists.

import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import { DEMO_USAGE, findDemoFixture } from "../src/demo/fixtures.ts";

const MAX_QUESTION_CHARS = 2000;

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let body = "";
    req.setEncoding("utf8");
    req.on("data", (chunk: string) => {
      body += chunk;
    });
    req.on("end", () => resolve(body));
    req.on("error", reject);
  });
}

function json(res: ServerResponse, status: number, payload: unknown): void {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(payload));
}

function authorised(req: IncomingMessage): boolean {
  return /^Bearer \S+$/.test(req.headers.authorization ?? "");
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function ask(req: IncomingMessage, res: ServerResponse): Promise<void> {
  if (!authorised(req)) {
    json(res, 401, { detail: "missing or invalid token", trace_id: "mock-401" });
    return;
  }
  let question = "";
  try {
    const parsed = JSON.parse(await readBody(req)) as { question?: unknown };
    question = typeof parsed.question === "string" ? parsed.question : "";
  } catch {
    json(res, 422, { detail: "body must be JSON", trace_id: "mock-422" });
    return;
  }
  if (question.trim().length === 0 || question.length > MAX_QUESTION_CHARS) {
    json(res, 422, { detail: "question length out of range", trace_id: "mock-422" });
    return;
  }
  const { response } = findDemoFixture(question);
  res.statusCode = 200;
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-store");
  await sleep(500);
  for (const word of response.answer.split(/(?<=\s)/)) {
    res.write(`event: token\ndata: ${JSON.stringify({ text: word })}\n\n`);
    await sleep(25);
  }
  res.end(`event: final\ndata: ${JSON.stringify({ ...response, bundle_version: "mock" })}\n\n`);
}

export function mockApi(): Plugin {
  return {
    name: "vigie-mock-api",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.method === "POST" && req.url === "/v1/ask") {
          ask(req, res).catch((error: unknown) => next(error));
          return;
        }
        if (req.method === "GET" && req.url === "/v1/usage/me") {
          if (!authorised(req)) json(res, 401, { detail: "missing or invalid token" });
          else json(res, 200, DEMO_USAGE);
          return;
        }
        next();
      });
    },
  };
}
