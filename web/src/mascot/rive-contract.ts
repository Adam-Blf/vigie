// The Rive contract from brief 11.6, checked the same way by the app (before trusting a
// .riv file) and by scripts/check-rive.ts (before accepting a delivery).

export const RIVE_ARTBOARD = "Vigie";
export const RIVE_STATE_MACHINE = "vigie";

export type RiveInputKind = "number" | "boolean" | "trigger";

export const RIVE_INPUTS: Record<string, RiveInputKind> = {
  state: "number",
  dark: "boolean",
  reset: "trigger",
};

export interface FoundInput {
  name: string;
  kind: RiveInputKind | "unknown";
}

export function riveContractProblems(inputs: readonly FoundInput[]): string[] {
  const problems: string[] = [];
  for (const [name, kind] of Object.entries(RIVE_INPUTS)) {
    const found = inputs.find((input) => input.name === name);
    if (!found) problems.push(`missing input "${name}" (${kind})`);
    else if (found.kind !== kind) problems.push(`input "${name}" is ${found.kind}, expected ${kind}`);
  }
  return problems;
}
