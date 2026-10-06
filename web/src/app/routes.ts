// Route table and a tiny History API router. Nine screens do not justify a routing
// library, and fewer kilobytes keep the first load under the 120 KB budget.

import { useEffect, useState } from "preact/hooks";

export const ROUTES = {
  chat: "/",
  settings: "/settings",
  usage: "/usage",
  about: "/about",
  legal: "/legal",
  privacy: "/privacy",
  offline: "/offline",
  error: "/error",
} as const;

export type RouteName = keyof typeof ROUTES | "notFound";

export function routeFor(pathname: string): RouteName {
  const clean = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const entry = Object.entries(ROUTES).find(([, path]) => path === clean);
  return entry ? (entry[0] as RouteName) : "notFound";
}

const NAVIGATE_EVENT = "vigie:navigate";

export function navigate(path: string): void {
  if (path === window.location.pathname) return;
  // The query string is kept so demo mode survives in-app navigation.
  window.history.pushState(null, "", `${path}${window.location.search}`);
  window.dispatchEvent(new Event(NAVIGATE_EVENT));
}

export function usePathname(): string {
  const [pathname, setPathname] = useState(window.location.pathname);
  useEffect(() => {
    const update = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", update);
    window.addEventListener(NAVIGATE_EVENT, update);
    return () => {
      window.removeEventListener("popstate", update);
      window.removeEventListener(NAVIGATE_EVENT, update);
    };
  }, []);
  return pathname;
}

// Lets plain <a href> links use the router while keeping middle-click and modifiers.
export function onLinkClick(event: MouseEvent, path: string): void {
  if (event.defaultPrevented || event.button !== 0) return;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  navigate(path);
}
