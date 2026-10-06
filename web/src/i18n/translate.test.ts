import { describe, expect, it } from "vitest";
import { en } from "./en.ts";
import { fr } from "./fr.ts";
import { detectLocale, isLocale, translate } from "./translate.ts";

const NBSP = String.fromCharCode(0xa0);
// Built from code points so this file never contains the characters it hunts for.
const FORBIDDEN = new RegExp(`[${String.fromCharCode(0x2014, 0x2013, 0xb7)}]`);

describe("dictionaries", () => {
  it("have exactly the same keys", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(fr).sort());
  });

  it("have no empty message", () => {
    for (const dictionary of [fr, en]) {
      for (const [key, value] of Object.entries(dictionary)) {
        expect(value.trim(), key).not.toBe("");
      }
    }
  });

  it("use the same placeholders in both languages", () => {
    const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const key of Object.keys(fr) as (keyof typeof fr)[]) {
      expect(placeholders(en[key]), key).toEqual(placeholders(fr[key]));
    }
  });

  it("put a no-break space before French high punctuation", () => {
    for (const [key, value] of Object.entries(fr)) {
      // URLs such as https:// are the one legitimate colon without a space.
      const text = value.replace(/https?:\/\/\S+/g, "");
      expect(text, key).not.toMatch(/ [:;?!]/);
      expect(text, key).not.toMatch(/[^\s (][;?!]/u);
    }
    expect(fr["chat.example.1"].endsWith(`${NBSP}?`)).toBe(true);
  });

  it("never contain em dashes, en dashes or middle dots", () => {
    for (const dictionary of [fr, en]) {
      for (const [key, value] of Object.entries(dictionary)) {
        expect(value, key).not.toMatch(FORBIDDEN);
      }
    }
  });

  it("carry the mandatory AI Act and legal mentions", () => {
    expect(fr["banner.ai"]).toContain("Vous parlez à une IA");
    expect(fr["banner.ai"]).toContain("pas un conseil juridique");
    expect(fr["banner.ai"]).toContain("Journal officiel de l'Union européenne font foi");
    expect(fr["answer.aiNotice"]).toBe("Réponse générée par une IA, à vérifier dans le texte officiel.");
    expect(fr["chat.privacy"]).toBe("Ne saisissez aucune donnée confidentielle ou personnelle.");
    expect(fr["footer.source"]).toContain("EUR-Lex");
    expect(fr["footer.source"]).toContain("2011/833/UE");
  });
});

describe("translate", () => {
  it("interpolates variables and keeps unknown placeholders visible", () => {
    expect(translate("fr", "chat.counter", { count: 12, max: "2 000" })).toBe("12 / 2 000 caractères");
    expect(translate("en", "chat.counter", { count: 3 })).toBe("3 / {max} characters");
  });

  it("detects English only when the browser asks for it", () => {
    expect(detectLocale(["en-GB", "fr"])).toBe("en");
    expect(detectLocale(["fr-FR"])).toBe("fr");
    expect(detectLocale(["de-DE"])).toBe("fr");
    expect(detectLocale([])).toBe("fr");
  });

  it("recognises supported locales", () => {
    expect(isLocale("fr")).toBe(true);
    expect(isLocale("de")).toBe(false);
    expect(isLocale(null)).toBe(false);
  });
});
