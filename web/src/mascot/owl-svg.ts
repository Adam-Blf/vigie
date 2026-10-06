// Fallback owl, drawn in code until the designer's SVGs and Rive file arrive.
// One geometric silhouette, two colours plus brass, and the spyglass doing the acting.
// scripts/export-mascot.ts writes these strings to public/mascot/static, and a unit
// test keeps the committed files in sync with this source.

import type { MascotState } from "./state.ts";

export type MascotTheme = "light" | "dark";

interface OwlPalette {
  body: string;
  face: string;
  brass: string;
  danger: string;
}

// Same values as the --color-mascot-* tokens; static files cannot read CSS variables.
export const OWL_PALETTES: Record<MascotTheme, OwlPalette> = {
  light: { body: "#24434b", face: "#e4ece9", brass: "#b9782a", danger: "#b3261e" },
  dark: { body: "#9fc4cb", face: "#17292d", brass: "#e0a25c", danger: "#ff8a80" },
};

const SILHOUETTE =
  "M44 58 L39 28 L63 45 Q80 39 97 45 L121 28 L116 58 Q127 82 122 110 " +
  "Q115 147 80 148 Q45 147 38 110 Q33 82 44 58 Z";

// Spyglass poses: [x, y, rotation] of a tube drawn from its eyepiece end.
const GLASS_POSE: Record<MascotState, [number, number, number]> = {
  idle: [100, 112, 28],
  listening: [100, 112, 28],
  searching: [104, 66, -4],
  found: [102, 108, 12],
  unknown: [100, 114, 40],
  blocked: [100, 114, 40],
  error: [98, 120, 74],
};

function spyglass(state: MascotState, p: OwlPalette): string {
  const [x, y, angle] = GLASS_POSE[state];
  return (
    `<g class="glass" transform="translate(${x} ${y}) rotate(${angle})">` +
    `<rect x="0" y="-5" width="18" height="10" rx="2" fill="${p.brass}"/>` +
    `<rect x="16" y="-6.5" width="16" height="13" rx="2" fill="${p.brass}"/>` +
    `<rect x="30" y="-8" width="12" height="16" rx="2.5" fill="${p.brass}"/>` +
    `<rect x="40" y="-7" width="3" height="14" rx="1" fill="${p.body}" opacity="0.35"/>` +
    `</g>`
  );
}

function eye(cx: number, state: MascotState, p: OwlPalette): string {
  const disc = `<circle cx="${cx}" cy="72" r="17" fill="${p.face}"/>`;
  if (state === "found") {
    // Smiling eyes: a closed upward arc reads as satisfaction at 24 px.
    return (
      disc +
      `<path d="M${cx - 8} 75 Q${cx} 64 ${cx + 8} 75" fill="none" stroke="${p.body}" ` +
      `stroke-width="4" stroke-linecap="round"/>`
    );
  }
  const shift: Record<MascotState, [number, number]> = {
    idle: [0, 0],
    listening: [3, 4],
    searching: [2, 0],
    found: [0, 0],
    unknown: [-2, -2],
    blocked: [0, 1],
    error: [0, 3],
  };
  const [dx, dy] = shift[state];
  const r = state === "error" ? 5 : 7;
  const lid =
    state === "blocked"
      ? `<rect x="${cx - 18}" y="54" width="36" height="14" fill="${p.body}"/>`
      : state === "error"
        ? `<path d="M${cx - 18} 56 L${cx + 18} 56 L${cx + (cx < 80 ? 18 : -18)} 70 Z" fill="${p.body}"/>`
        : "";
  return (
    disc +
    `<circle cx="${cx + dx}" cy="${72 + dy}" r="${r}" fill="${p.body}"/>` +
    `<circle cx="${cx + dx + 2}" cy="${70 + dy}" r="1.8" fill="${p.face}"/>` +
    lid +
    `<ellipse class="lid" cx="${cx}" cy="72" rx="17.5" ry="17.5" fill="${p.body}"/>`
  );
}

function extras(state: MascotState, p: OwlPalette): string {
  switch (state) {
    case "unknown":
      return (
        `<path d="M128 22 Q128 12 138 12 Q148 12 148 21 Q148 28 139 31 L139 37" fill="none" ` +
        `stroke="${p.brass}" stroke-width="5" stroke-linecap="round"/>` +
        `<circle cx="139" cy="46" r="3.2" fill="${p.brass}"/>`
      );
    case "blocked":
      return (
        `<g class="shield"><path d="M80 92 L112 102 Q112 134 80 150 Q48 134 48 102 Z" ` +
        `fill="${p.danger}"/>` +
        // A barrier bar, not a tick: a tick would read as "approved".
        `<path d="M66 118 L94 118" stroke="${p.face}" stroke-width="7" stroke-linecap="round"/></g>`
      );
    case "error":
      return (
        `<path d="M58 44 L62 34 L67 43 L72 33 L76 42" fill="none" stroke="${p.body}" ` +
        `stroke-width="4" stroke-linejoin="round"/>` +
        `<path d="M86 42 L91 33 L95 43 L100 34 L103 44" fill="none" stroke="${p.body}" ` +
        `stroke-width="4" stroke-linejoin="round"/>`
      );
    default:
      return "";
  }
}

const HEAD_TILT: Partial<Record<MascotState, number>> = { listening: -6, unknown: 9 };

// Motion only runs when the reader has not asked for less of it.
const ANIMATIONS: Record<MascotState, string> = {
  idle:
    ".lid{transform-box:fill-box;transform-origin:center;transform:scaleY(0);animation:blink 4s infinite}" +
    ".owl{transform-origin:80px 148px;animation:breathe 4s ease-in-out infinite}",
  listening: ".owl{transform-origin:80px 148px;animation:lean 1.6s ease-in-out infinite alternate}",
  searching: ".glass{animation:sweep 1.8s ease-in-out infinite alternate}",
  found: ".owl{animation:nod .5s ease-out 2}",
  unknown: ".owl{transform-origin:80px 148px;animation:shrug .7s ease-out 1}",
  blocked: ".shield{animation:flash .45s ease-out 2}",
  error: ".owl{animation:shake .4s ease-in-out 2}",
};

const KEYFRAMES =
  "@keyframes blink{0%,92%,100%{transform:scaleY(0)}95%{transform:scaleY(1)}}" +
  "@keyframes breathe{50%{transform:scale(1.015)}}" +
  "@keyframes lean{to{transform:rotate(-3deg)}}" +
  "@keyframes sweep{from{translate:0 0;rotate:-6deg}to{translate:0 -3px;rotate:6deg}}" +
  "@keyframes nod{50%{transform:translateY(4px)}}" +
  "@keyframes shrug{40%{transform:translateY(-4px)}}" +
  "@keyframes flash{50%{opacity:.55}}" +
  "@keyframes shake{25%{transform:translateX(-3px)}75%{transform:translateX(3px)}}";

export interface OwlOptions {
  animated?: boolean;
}

export function renderOwlSvg(
  state: MascotState,
  theme: MascotTheme,
  options: OwlOptions = {},
): string {
  const p = OWL_PALETTES[theme];
  const animated = options.animated ?? true;
  const lidHidden = ".lid{transform:scaleY(0)}";
  const style = animated
    ? `<style>${lidHidden}.lid,.glass{transform-box:fill-box}` +
      `@media (prefers-reduced-motion:no-preference){${ANIMATIONS[state]}${KEYFRAMES}}</style>`
    : `<style>${lidHidden}</style>`;
  const tilt = HEAD_TILT[state];
  const tiltAttr = tilt ? ` transform="rotate(${tilt} 80 100)"` : "";
  const belly =
    `<path d="M66 112 L72 117 L78 112 M82 112 L88 117 L94 112 M74 124 L80 129 L86 124" ` +
    `fill="none" stroke="${p.face}" stroke-width="2.5" stroke-linecap="round" opacity="0.55"/>`;
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" width="160" height="160">` +
    style +
    `<g class="owl"><g${tiltAttr}>` +
    `<path d="${SILHOUETTE}" fill="${p.body}"/>` +
    eye(64, state, p) +
    eye(96, state, p) +
    `<path d="M75 85 L85 85 L80 95 Z" fill="${p.brass}"/>` +
    belly +
    `<rect x="66" y="144" width="10" height="6" rx="3" fill="${p.brass}"/>` +
    `<rect x="84" y="144" width="10" height="6" rx="3" fill="${p.brass}"/>` +
    `</g>${spyglass(state, p)}${extras(state, p)}</g></svg>`
  );
}

export function mascotFileName(state: MascotState | "poster", theme: MascotTheme): string {
  return theme === "light" ? `vigie-mascot-${state}.svg` : `vigie-mascot-${state}-dark.svg`;
}
