// Demo client: same interface as the HTTP client, answers from the frozen fixtures and
// streams them word by word so the demo looks like the real thing. No network at all.

import { ApiError } from "../api/errors.ts";
import type { ApiClient } from "../api/types.ts";
import { DEMO_USAGE, findDemoFixture } from "./fixtures.ts";

export interface DemoTiming {
  firstTokenMs: number;
  perWordMs: number;
}

const DEFAULT_TIMING: DemoTiming = { firstTokenMs: 700, perWordMs: 28 };

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new ApiError("aborted", "request cancelled"));
      return;
    }
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new ApiError("aborted", "request cancelled"));
      },
      { once: true },
    );
  });
}

export function createDemoClient(timing: DemoTiming = DEFAULT_TIMING): ApiClient {
  return {
    async ask(question, handlers, signal) {
      const { response } = findDemoFixture(question);
      await wait(timing.firstTokenMs, signal);
      const words = response.answer.split(/(?<=\s)/);
      for (const word of words) {
        handlers.onToken(word);
        await wait(timing.perWordMs, signal);
      }
      return structuredClone(response);
    },
    async usage(signal) {
      await wait(0, signal);
      return { ...DEMO_USAGE };
    },
  };
}
