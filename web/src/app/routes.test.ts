import { afterEach, describe, expect, it, vi } from "vitest";
import { navigate, onLinkClick, routeFor } from "./routes.ts";

describe("routeFor", () => {
  it("maps known paths, with or without a trailing slash", () => {
    expect(routeFor("/")).toBe("chat");
    expect(routeFor("/settings")).toBe("settings");
    expect(routeFor("/privacy/")).toBe("privacy");
    expect(routeFor("/error")).toBe("error");
  });

  it("sends anything else to the 404 screen", () => {
    expect(routeFor("/admin")).toBe("notFound");
    expect(routeFor("/settings/extra")).toBe("notFound");
  });
});

describe("navigate", () => {
  afterEach(() => window.history.replaceState(null, "", "/"));

  it("keeps the query string so demo mode survives navigation", () => {
    window.history.replaceState(null, "", "/?demo=1");
    const listener = vi.fn();
    window.addEventListener("vigie:navigate", listener);
    navigate("/about");
    expect(window.location.pathname).toBe("/about");
    expect(window.location.search).toBe("?demo=1");
    expect(listener).toHaveBeenCalledOnce();
    navigate("/about");
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener("vigie:navigate", listener);
  });

  it("lets modified clicks open a new tab instead of routing", () => {
    const plain = new MouseEvent("click", { button: 0, cancelable: true });
    onLinkClick(plain, "/usage");
    expect(plain.defaultPrevented).toBe(true);
    expect(window.location.pathname).toBe("/usage");
    const withCtrl = new MouseEvent("click", { button: 0, ctrlKey: true, cancelable: true });
    onLinkClick(withCtrl, "/legal");
    expect(withCtrl.defaultPrevented).toBe(false);
    expect(window.location.pathname).toBe("/usage");
  });
});
