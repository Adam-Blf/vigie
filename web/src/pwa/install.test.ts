import { describe, expect, it } from "vitest";
import { shouldOfferInstall } from "./install.ts";

describe("install offer", () => {
  it("shows once, after the third question, when the browser allows it", () => {
    expect(shouldOfferInstall(2, false, true)).toBe(false);
    expect(shouldOfferInstall(3, false, true)).toBe(true);
    expect(shouldOfferInstall(5, true, true)).toBe(false);
    expect(shouldOfferInstall(5, false, false)).toBe(false);
  });
});
