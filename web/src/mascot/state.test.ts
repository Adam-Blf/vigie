import { describe, expect, it } from "vitest";
import {
  MASCOT_STATES,
  MIN_HOLD_MS,
  nextShownState,
  resolveMascotState,
  RIVE_STATE_INDEX,
  type MascotSignals,
} from "./state.ts";

const none: MascotSignals = {
  error: false,
  blocked: false,
  unknown: false,
  found: false,
  searching: false,
  listening: false,
};

describe("resolveMascotState", () => {
  it("is idle when nothing happens", () => {
    expect(resolveMascotState(none)).toBe("idle");
  });

  it("maps each lone signal to its own state", () => {
    for (const signal of Object.keys(none) as (keyof MascotSignals)[]) {
      expect(resolveMascotState({ ...none, [signal]: true })).toBe(signal);
    }
  });

  it("follows the priority error, blocked, unknown, found, searching, listening", () => {
    const order: (keyof MascotSignals)[] = ["error", "blocked", "unknown", "found", "searching", "listening"];
    // For every pair, the higher one wins whatever else is set below it.
    order.forEach((winner, index) => {
      const signals = { ...none };
      for (const lower of order.slice(index)) signals[lower] = true;
      expect(resolveMascotState(signals)).toBe(winner);
    });
    expect(resolveMascotState({ ...none, listening: true, error: true })).toBe("error");
    expect(resolveMascotState({ ...none, found: true, blocked: true })).toBe("blocked");
  });
});

describe("Rive state index", () => {
  it("numbers the seven states 0 to 6 in contract order", () => {
    expect(MASCOT_STATES.map((state) => RIVE_STATE_INDEX[state])).toEqual([0, 1, 2, 3, 4, 5, 6]);
  });
});

describe("nextShownState", () => {
  it("holds searching for at least 600 ms", () => {
    expect(MIN_HOLD_MS.searching).toBe(600);
    expect(nextShownState({ state: "searching", since: 0 }, "found", 200)).toEqual({
      state: "searching",
      waitMs: 400,
    });
    expect(nextShownState({ state: "searching", since: 0 }, "found", 600)).toEqual({
      state: "found",
      waitMs: 0,
    });
  });

  it("holds found for at least 1.5 s", () => {
    expect(nextShownState({ state: "found", since: 1000 }, "idle", 2000)).toEqual({
      state: "found",
      waitMs: 500,
    });
    expect(nextShownState({ state: "found", since: 1000 }, "idle", 2500).state).toBe("idle");
  });

  it("switches at once from states without a minimum", () => {
    expect(nextShownState({ state: "idle", since: 0 }, "listening", 1)).toEqual({
      state: "listening",
      waitMs: 0,
    });
  });

  it("does nothing when the wanted state is already shown", () => {
    expect(nextShownState({ state: "found", since: 0 }, "found", 10)).toEqual({ state: "found", waitMs: 0 });
  });
});
