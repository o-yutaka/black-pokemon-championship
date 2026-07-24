import { describe, expect, it } from "vitest";
import { cardArtUrl } from "./cardArt";


describe("real card artwork", () => {
  it("prefers replay-provided exact artwork", () => {
    expect(cardArtUrl(10, "https://example.com/exact.png", new Map([[10, "https://example.com/catalog.png"]]))).toBe("https://example.com/exact.png");
  });

  it("uses the resolved catalog image and otherwise fails closed", () => {
    expect(cardArtUrl(10, null, new Map([[10, "https://example.com/catalog.png"]]))).toBe("https://example.com/catalog.png");
    expect(cardArtUrl(11, null, new Map())).toBeNull();
  });
});
