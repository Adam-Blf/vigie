// The owl. A static SVG paints first (no layout shift, no script needed); the Rive
// animation replaces it later, only if a .riv is configured, motion is welcome and the
// browser is idle. Any failure quietly keeps the SVG.

import { useEffect, useRef, useState } from "preact/hooks";
import { useApp } from "../app/context.ts";
import { useEffectiveTheme, useReducedMotion } from "../app/useEnvironment.ts";
import { mascotFileName } from "./owl-svg.ts";
import type { RiveHandle } from "./rive-loader.ts";
import type { MascotState } from "./state.ts";

interface MascotProps {
  state: MascotState;
  size: number;
}

function whenIdle(callback: () => void): () => void {
  if ("requestIdleCallback" in window) {
    const id = window.requestIdleCallback(callback, { timeout: 3000 });
    return () => window.cancelIdleCallback(id);
  }
  const id = setTimeout(callback, 1200);
  return () => clearTimeout(id);
}

export function Mascot({ state, size }: MascotProps) {
  const { config, theme, t } = useApp();
  const effective = useEffectiveTheme(theme);
  const reducedMotion = useReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const handleRef = useRef<RiveHandle | null>(null);
  const [riveReady, setRiveReady] = useState(false);
  const riveUrl = reducedMotion ? null : config.riveUrl;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!riveUrl || !canvas) return undefined;
    let cancelled = false;
    const cancelIdle = whenIdle(() => {
      import("./rive-loader.ts")
        .then(({ mountRive }) => mountRive(canvas, riveUrl, state, effective === "dark"))
        .then((handle) => {
          if (cancelled) {
            handle.destroy();
            return;
          }
          handleRef.current = handle;
          setRiveReady(true);
        })
        .catch(() => setRiveReady(false));
    });
    // A hidden tab has nobody to watch the owl, so the animation loop stops.
    const onVisibility = () => {
      if (document.hidden) handleRef.current?.pause();
      else handleRef.current?.play();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelled = true;
      cancelIdle();
      document.removeEventListener("visibilitychange", onVisibility);
      handleRef.current?.destroy();
      handleRef.current = null;
      setRiveReady(false);
    };
    // Only a new file remounts the runtime. State and theme are pushed by the two effects
    // below, otherwise every state change would rebuild the whole animation.
  }, [riveUrl]);

  useEffect(() => handleRef.current?.setState(state), [state]);
  useEffect(() => handleRef.current?.setDark(effective === "dark"), [effective]);

  const src = `/mascot/static/${mascotFileName(state, effective)}`;
  return (
    <div class="mascot" data-state={state} style={{ width: `${size}px`, height: `${size}px` }}>
      <div aria-hidden="true" class="mascot-art">
        {riveUrl && (
          <canvas ref={canvasRef} width={size * 2} height={size * 2} hidden={!riveReady} />
        )}
        {!riveReady && <img src={src} width={size} height={size} alt="" decoding="async" />}
      </div>
      <span class="sr-only">{t(`mascot.${state}`)}</span>
    </div>
  );
}
