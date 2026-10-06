// Acceptance gate for the designer's Rive file: loads public/mascot/vigie-mascot.riv in
// Chromium with the local runtime and fails if the file, the artboard, the state machine
// or one of the contract inputs is missing, or if the file is over 150 KB.
// Usage: node scripts/check-rive.ts [path/to/file.riv]

import { existsSync, readFileSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import {
  RIVE_ARTBOARD,
  RIVE_STATE_MACHINE,
  riveContractProblems,
  type FoundInput,
} from "../src/mascot/rive-contract.ts";

const MAX_BYTES = 150 * 1024;
const ORIGIN = "http://rive.check";

async function inputsOf(file: string): Promise<FoundInput[]> {
  const require = createRequire(import.meta.url);
  const runtime = readFileSync(require.resolve("@rive-app/canvas/rive.js"));
  const wasm = readFileSync(require.resolve("@rive-app/canvas/rive.wasm"));
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    // Everything is served from memory: the check never touches the network.
    await page.route(`${ORIGIN}/**`, (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/rive.js") return route.fulfill({ body: runtime, contentType: "text/javascript" });
      if (path === "/rive.wasm") return route.fulfill({ body: wasm, contentType: "application/wasm" });
      if (path === "/mascot.riv") return route.fulfill({ body: readFileSync(file) });
      return route.fulfill({ body: "<canvas id=c width=96 height=96></canvas><script src=/rive.js></script>", contentType: "text/html" });
    });
    await page.goto(`${ORIGIN}/`);
    return await page.evaluate(
      ([artboard, machine]) =>
        new Promise<FoundInput[]>((resolve, reject) => {
          const rive = (window as unknown as { rive: typeof import("@rive-app/canvas") }).rive;
          rive.RuntimeLoader.setWasmUrl("/rive.wasm");
          const instance = new rive.Rive({
            src: "/mascot.riv",
            canvas: document.getElementById("c") as HTMLCanvasElement,
            artboard,
            stateMachines: machine,
            onLoadError: () => reject(new Error(`unreadable file, or no artboard "${artboard}" with state machine "${machine}"`)),
            onLoad: () => {
              const kinds: Record<number, FoundInput["kind"]> = {
                [rive.StateMachineInputType.Number]: "number",
                [rive.StateMachineInputType.Boolean]: "boolean",
                [rive.StateMachineInputType.Trigger]: "trigger",
              };
              resolve(
                (instance.stateMachineInputs(machine) ?? []).map((input) => ({
                  name: input.name,
                  kind: kinds[input.type] ?? "unknown",
                })),
              );
            },
          });
        }),
      [RIVE_ARTBOARD, RIVE_STATE_MACHINE] as const,
    );
  } finally {
    await browser.close();
  }
}

async function main(): Promise<number> {
  const file = process.argv[2] ?? fileURLToPath(new URL("../public/mascot/vigie-mascot.riv", import.meta.url));
  if (!existsSync(file)) {
    console.log(`FAIL no Rive file at ${file}`);
    return 1;
  }
  const problems: string[] = [];
  const size = statSync(file).size;
  if (size > MAX_BYTES) problems.push(`file is ${Math.round(size / 1024)} KB, limit is 150 KB`);
  try {
    problems.push(...riveContractProblems(await inputsOf(file)));
  } catch (error) {
    problems.push(error instanceof Error ? error.message : String(error));
  }
  for (const problem of problems) console.log(`FAIL ${problem}`);
  if (problems.length === 0) console.log("check-rive: contract respected");
  return problems.length === 0 ? 0 : 1;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  process.exitCode = await main();
}
