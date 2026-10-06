// Applies the minimum display times of state.ts to a live stream of wanted states.

import { useEffect, useRef, useState } from "preact/hooks";
import { nextShownState, type MascotState, type Shown } from "./state.ts";

export function useShownState(wanted: MascotState): MascotState {
  const [shown, setShown] = useState<Shown>(() => ({ state: wanted, since: Date.now() }));
  const shownRef = useRef(shown);
  shownRef.current = shown;

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const step = () => {
      const next = nextShownState(shownRef.current, wanted, Date.now());
      if (next.waitMs > 0) {
        timer = setTimeout(step, next.waitMs);
      } else if (next.state !== shownRef.current.state) {
        setShown({ state: next.state, since: Date.now() });
      }
    };
    step();
    return () => clearTimeout(timer);
  }, [wanted]);

  return shown.state;
}
