import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

function source(name: string): string {
  return readFileSync(new URL(name, import.meta.url), "utf8");
}

describe("Battle Studio layout repair contract", () => {
  it("uses content-responsive folder cards instead of a fixed four-column grid", () => {
    const nativeCss = source("./native-runtime.css");
    expect(nativeCss).toContain("repeat(auto-fit");
    expect(nativeCss).toContain("overflow-wrap: anywhere");
    expect(nativeCss).not.toContain("repeat(4,minmax(0,1fr))");
  });

  it("keeps real card artwork complete rather than cropping it", () => {
    const layoutCss = source("./layout-repair.css");
    const boardSource = source("./BattleBoard.tsx");
    expect(layoutCss).toContain("object-fit: contain");
    expect(layoutCss).toContain("aspect-ratio: 63 / 88");
    expect(boardSource).toContain("<img src={resolvedImageUrl!}");
    expect(boardSource).not.toContain("backgroundImage: `url(${imageUrl})`");
  });

  it("prevents mobile sticky panels and horizontal overflow from stacking", () => {
    const layoutCss = source("./layout-repair.css");
    expect(layoutCss).toContain("overflow-x: clip");
    expect(layoutCss).toContain(".engine-runbar");
    expect(layoutCss).toContain("position: static !important");
    expect(layoutCss).toContain("grid-template-columns: minmax(0, 1fr) auto auto");
  });
});
