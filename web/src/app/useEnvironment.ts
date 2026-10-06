// Small hooks that follow the browser: system theme, reduced motion, connectivity.

import { useEffect, useState } from "preact/hooks";
import type { EffectiveTheme, ThemeChoice } from "../lib/theme.ts";

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const list = window.matchMedia(query);
    const update = () => setMatches(list.matches);
    update();
    list.addEventListener("change", update);
    return () => list.removeEventListener("change", update);
  }, [query]);
  return matches;
}

export function useEffectiveTheme(choice: ThemeChoice): EffectiveTheme {
  const systemDark = useMediaQuery("(prefers-color-scheme: dark)");
  if (choice !== "system") return choice;
  return systemDark ? "dark" : "light";
}

export function useReducedMotion(): boolean {
  return useMediaQuery("(prefers-reduced-motion: reduce)");
}

export function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  return online;
}
