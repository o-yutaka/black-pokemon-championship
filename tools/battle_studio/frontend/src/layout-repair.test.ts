import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

function source(name: string): string {
  return readFileSync(new URL(name, import.meta.url), "utf8");
}

describe("Battle Studio layout repair contract", () => {
  it("uses content-responsive folder cards instead of a fixed four-column grid", () => {
    const css = source("./native-runtime.css");
    expect(css).toContain("repeat(auto-fit");
    expect(css).toContain("overflow-wrap: anywhere");
    expect(css).not.toContain("repeat(4,minmax(0,1fr))");
  });

  it("keeps real card artwork complete rather than cropping it", () => {
    const css = source("./layout-repair.css");
    const board = source("./BattleBoard.tsx");
    expect(css).toContain("object-fit: contain");
    expect(css).toContain("aspect-ratio: 63 / 88");
    expect(board).toContain("<img src={resolvedImageUrl!}");
    expect(board).not.toContain("backgroundImage: `url(${imageUrl})`");
  });

  it("prevents mobile sticky panels and horizontal overflow from stacking", () => {
    const css = source("./layout-repair.css");
    expect(css).toContain("overflow-x: clip");
    expect(css).toContain(".engine-runbar");
    expect(css).toContain("position: static !important");
    expect(css).toContain("grid-template-columns: minmax(0, 1fr) auto auto");
  });
});
