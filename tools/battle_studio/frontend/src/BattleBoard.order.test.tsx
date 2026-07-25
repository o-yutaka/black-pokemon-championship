import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { BattleBoard } from "./BattleBoard";
import { demoReplay } from "./demo";

const EXPECTED_MARKERS = [
  "opponent-info",
  "opponent-bench",
  "opponent-active",
  "center",
  "self-active",
  "self-bench",
  "self-info",
];

function renderedBoard(): string {
  return renderToStaticMarkup(
    <BattleBoard
      frame={demoReplay.frames[0]}
      previousFrame={null}
      onSelect={() => undefined}
      catalog={new Map()}
      motionMode="lite"
    />,
  );
}

describe("BattleBoard visual order", () => {
  it("places both active spots next to the center line", () => {
    const markup = renderedBoard();
    const actual = EXPECTED_MARKERS
      .map((marker) => ({ marker, index: markup.indexOf(`data-board-marker=\"${marker}\"`) }))
      .sort((left, right) => left.index - right.index)
      .map(({ marker }) => marker);

    expect(actual).toEqual(EXPECTED_MARKERS);
  });

  it("does not print opaque runtime identifiers on the playmat", () => {
    const markup = renderedBoard();
    expect(markup).not.toContain("カード識別");
    expect(markup).not.toMatch(/#\d{5,}/);
  });
});
