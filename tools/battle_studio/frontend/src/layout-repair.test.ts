import { describe, expect, it } from "vitest";
import boardSource from "./BattleBoard.tsx?raw";
import layoutCss from "./layout-repair.css?raw";
import nativeCss from "./native-runtime.css?raw";

describe("Battle Studio layout repair contract", () => {
  it("uses content-responsive folder cards instead of a fixed four-column grid", () => {
    expect(nativeCss).toContain("repeat(auto-fit");
    expect(nativeCss).toContain("overflow-wrap: anywhere");
    expect(nativeCss).not.toContain("repeat(4,minmax(0,1fr))");
  });

  it("keeps real card artwork complete rather than cropping it", () => {
    expect(layoutCss).toContain("object-fit: contain");
    expect(layoutCss).toContain("aspect-ratio: 63 / 88");
    expect(boardSource).toContain("<img src={resolvedImageUrl!}");
    expect(boardSource).not.toContain("backgroundImage: `url(${imageUrl})`");
  });

  it("prevents mobile sticky panels and horizontal overflow from stacking", () => {
    expect(layoutCss).toContain("overflow-x: clip");
    expect(layoutCss).toContain(".engine-runbar");
    expect(layoutCss).toContain("position: static !important");
    expect(layoutCss).toContain("grid-template-columns: minmax(0, 1fr) auto auto");
  });
});
