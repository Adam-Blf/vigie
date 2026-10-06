import type { IconName } from "./icon-names.ts";

// Icons are always decorative here: the button or text next to them carries the meaning.
export function Icon({ name }: { name: IconName }) {
  return <i class={`ph ph-${name}`} aria-hidden="true" />;
}
