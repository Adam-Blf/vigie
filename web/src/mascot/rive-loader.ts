// Loads the designer's Rive mascot on demand. Imported dynamically, so the 2 MB runtime
// and its WebAssembly never weigh on the first load, and only when a .riv is configured.

import { RIVE_STATE_INDEX, type MascotState } from "./state.ts";
import {
  RIVE_ARTBOARD,
  RIVE_STATE_MACHINE,
  riveContractProblems,
  type FoundInput,
} from "./rive-contract.ts";

export interface RiveHandle {
  setState(state: MascotState): void;
  setDark(dark: boolean): void;
  pause(): void;
  play(): void;
  destroy(): void;
}

export async function mountRive(
  canvas: HTMLCanvasElement,
  src: string,
  state: MascotState,
  dark: boolean,
): Promise<RiveHandle> {
  const rive = await import("@rive-app/canvas");
  rive.RuntimeLoader.setWasmUrl("/vendor/rive.wasm");
  return new Promise((resolve, reject) => {
    const instance = new rive.Rive({
      src,
      canvas,
      artboard: RIVE_ARTBOARD,
      stateMachines: RIVE_STATE_MACHINE,
      autoplay: true,
      onLoadError: () => reject(new Error("rive file failed to load")),
      onLoad: () => {
        const inputs = instance.stateMachineInputs(RIVE_STATE_MACHINE) ?? [];
        const kinds: FoundInput[] = inputs.map((input) => ({
          name: input.name,
          kind:
            input.type === rive.StateMachineInputType.Number
              ? "number"
              : input.type === rive.StateMachineInputType.Boolean
                ? "boolean"
                : input.type === rive.StateMachineInputType.Trigger
                  ? "trigger"
                  : "unknown",
        }));
        const problems = riveContractProblems(kinds);
        if (problems.length > 0) {
          instance.cleanup();
          reject(new Error(`rive contract broken: ${problems.join(", ")}`));
          return;
        }
        const byName = (name: string) => inputs.find((input) => input.name === name);
        const handle: RiveHandle = {
          setState(next) {
            const input = byName("state");
            if (input) input.value = RIVE_STATE_INDEX[next];
          },
          setDark(isDark) {
            const input = byName("dark");
            if (input) input.value = isDark;
          },
          pause: () => instance.pause(),
          play: () => instance.play(),
          destroy: () => instance.cleanup(),
        };
        instance.resizeDrawingSurfaceToCanvas();
        handle.setState(state);
        handle.setDark(dark);
        resolve(handle);
      },
    });
  });
}
