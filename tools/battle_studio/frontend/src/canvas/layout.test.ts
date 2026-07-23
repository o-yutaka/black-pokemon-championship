import { describe, expect, it } from "vitest";
import { demoReplay } from "../demo";
import { computeBattleLayout, hitTestCard } from "./layout";

const frame = demoReplay.frames[0];

describe("canvas battle layout", () => {
  it("lays out every visible active and bench card with stable instance identity", () => {
    const layout = computeBattleLayout(1000, 720, frame);
    const expected = frame.players.reduce((count, player) => count + player.bench.length + (player.active ? 1 : 0), 0);
    expect(layout.cardNodes).toHaveLength(expected);
    expect(new Set(layout.cardNodes.map((node) => node.key)).size).toBe(expected);
  });

  it("hit tests the exact card instance instead of cardId", () => {
    const layout = computeBattleLayout(1000, 720, frame);
    const node = layout.cardNodes.find((value) => value.zone === "active" && value.playerIndex === 0)!;
    const card = hitTestCard(layout, node.rect.x + node.rect.width / 2, node.rect.y + node.rect.height / 2);
    expect(card?.serial).toBe(frame.players[0].active?.serial);
  });

  it("keeps cards inside the canvas on narrow iPhone-sized widths", () => {
    const layout = computeBattleLayout(390, 640, frame);
    for (const node of layout.cardNodes) {
      expect(node.rect.x).toBeGreaterThanOrEqual(0);
      expect(node.rect.y).toBeGreaterThanOrEqual(0);
      expect(node.rect.x + node.rect.width).toBeLessThanOrEqual(layout.width);
      expect(node.rect.y + node.rect.height).toBeLessThanOrEqual(layout.height);
    }
  });
});
