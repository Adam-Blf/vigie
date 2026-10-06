import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DEFAULT_CONFIG, isDemoRequested, loadConfig, parseConfig } from "./config.ts";
import { readItem, removeItem, writeItem } from "./storage.ts";
import { applyTheme, effectiveTheme, nextThemeChoice, readThemeChoice } from "./theme.ts";
import { clearToken, getToken, isRemembered, saveToken } from "./token.ts";

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

describe("token storage", () => {
  it("keeps the token for the tab only by default", () => {
    saveToken("  vig_abc  ", false);
    expect(sessionStorage.getItem("vigie.token")).toBe("vig_abc");
    expect(localStorage.getItem("vigie.token")).toBeNull();
    expect(getToken()).toBe("vig_abc");
    expect(isRemembered()).toBe(false);
  });

  it("uses device storage only when asked to stay signed in, and moves cleanly", () => {
    saveToken("vig_abc", true);
    expect(localStorage.getItem("vigie.token")).toBe("vig_abc");
    expect(isRemembered()).toBe(true);
    saveToken("vig_def", false);
    expect(localStorage.getItem("vigie.token")).toBeNull();
    expect(getToken()).toBe("vig_def");
  });

  it("clears both stores, and an empty token clears too", () => {
    saveToken("vig_abc", true);
    clearToken();
    expect(getToken()).toBeNull();
    saveToken("vig_abc", false);
    saveToken("   ", false);
    expect(getToken()).toBeNull();
  });
});

describe("storage wrappers", () => {
  it("survive a store that throws", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("full", "QuotaExceededError");
    });
    expect(() => writeItem("local", "k", "v")).not.toThrow();
    spy.mockRestore();
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    expect(readItem("local", "k")).toBeNull();
    get.mockRestore();
    const remove = vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    expect(() => removeItem("local", "k")).not.toThrow();
    remove.mockRestore();
  });
});

describe("runtime config", () => {
  it("accepts same-origin paths only", () => {
    expect(parseConfig({ apiBaseUrl: "/api", demoEnabled: true, riveUrl: "/mascot/vigie-mascot.riv" })).toEqual({
      apiBaseUrl: "/api",
      demoEnabled: true,
      riveUrl: "/mascot/vigie-mascot.riv",
    });
    expect(parseConfig({ apiBaseUrl: "https://evil.example", riveUrl: "//cdn.example/x.riv" })).toEqual(
      DEFAULT_CONFIG,
    );
    expect(parseConfig(null)).toEqual(DEFAULT_CONFIG);
    expect(parseConfig({ demoEnabled: "yes" }).demoEnabled).toBe(false);
  });

  it("falls back to defaults when config.json is missing or broken", async () => {
    const missing = vi.fn().mockResolvedValue(new Response(null, { status: 404 }));
    await expect(loadConfig(missing)).resolves.toEqual(DEFAULT_CONFIG);
    const offline = vi.fn().mockRejectedValue(new TypeError("offline"));
    await expect(loadConfig(offline)).resolves.toEqual(DEFAULT_CONFIG);
    const ok = vi.fn().mockResolvedValue(Response.json({ apiBaseUrl: "/x", demoEnabled: true }));
    await expect(loadConfig(ok)).resolves.toMatchObject({ apiBaseUrl: "/x", demoEnabled: true });
  });

  it("detects the demo flag", () => {
    expect(isDemoRequested("?demo=1")).toBe(true);
    expect(isDemoRequested("?demo=true")).toBe(false);
    expect(isDemoRequested("")).toBe(false);
  });
});

describe("theme", () => {
  afterEach(() => {
    delete document.documentElement.dataset.theme;
    document.head.innerHTML = "";
  });

  it("cycles system, light, dark", () => {
    expect(nextThemeChoice("system")).toBe("light");
    expect(nextThemeChoice("light")).toBe("dark");
    expect(nextThemeChoice("dark")).toBe("system");
  });

  it("writes data-theme and the theme-color metas, and forgets on system", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false }) as unknown as typeof window.matchMedia;
    for (const scheme of ["light", "dark"]) {
      const meta = document.createElement("meta");
      meta.name = "theme-color";
      meta.dataset.scheme = scheme;
      document.head.append(meta);
    }
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(readThemeChoice()).toBe("dark");
    const metas = [...document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')];
    expect(metas.map((m) => m.content)).toEqual(["#0d1719", "#0d1719"]);
    applyTheme("system");
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(readThemeChoice()).toBe("system");
    expect(metas.map((m) => m.content)).toEqual(["#f6f8f8", "#0d1719"]);
    expect(effectiveTheme("system")).toBe("light");
    expect(effectiveTheme("dark")).toBe("dark");
  });
});
