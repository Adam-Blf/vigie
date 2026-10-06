// Which face the owl shows, decided by pure functions so the rules are testable
// without a browser. The order mirrors brief 11.6: a problem always outranks progress.

export const MASCOT_STATES = [
  "idle",
  "listening",
  "searching",
  "found",
  "unknown",
  "blocked",
  "error",
] as const;
export type MascotState = (typeof MASCOT_STATES)[number];

// Numeric value of the Rive `state` input, fixed by the designer contract.
export const RIVE_STATE_INDEX: Record<MascotState, number> = {
  idle: 0,
  listening: 1,
  searching: 2,
  found: 3,
  unknown: 4,
  blocked: 5,
  error: 6,
};

export interface MascotSignals {
  error: boolean;
  blocked: boolean;
  unknown: boolean;
  found: boolean;
  searching: boolean;
  listening: boolean;
}

const PRIORITY: readonly (keyof MascotSignals)[] = [
  "error",
  "blocked",
  "unknown",
  "found",
  "searching",
  "listening",
];

export function resolveMascotState(signals: MascotSignals): MascotState {
  return PRIORITY.find((state) => signals[state]) ?? "idle";
}

// A flash of "searching" on a fast answer reads as a glitch, and "found" needs time
// to be noticed, so both are held on screen for a minimum duration.
export const MIN_HOLD_MS: Partial<Record<MascotState, number>> = {
  searching: 600,
  found: 1500,
};

export interface Shown {
  state: MascotState;
  since: number;
}

export interface Next {
  state: MascotState;
  waitMs: number;
}

export function nextShownState(shown: Shown, wanted: MascotState, now: number): Next {
  if (wanted === shown.state) return { state: shown.state, waitMs: 0 };
  const hold = MIN_HOLD_MS[shown.state] ?? 0;
  const elapsed = now - shown.since;
  if (elapsed < hold) return { state: shown.state, waitMs: hold - elapsed };
  return { state: wanted, waitMs: 0 };
}
