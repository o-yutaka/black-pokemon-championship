import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { BattleBoard } from "./BattleBoard";
import { battleFrameSchema, type CardInstance } from "./types";

function card(playerIndex: 0 | 1, serial: number, name: string, zone: CardInstance["zone"], slot: number | null = null): CardInstance {
  return {
    playerIndex,
    serial,
    cardId: serial + 1000,
    name,
    zone,
    slot,
    hp: zone === "active" || zone === "bench" ? 100 : null,
    maxHp: zone === "active" || zone === "bench" ? 100 : null,
    damage: 0,
    energies: [],
    tools: [],
    status: [],
    evolution: [],
    imageUrl: `https://images.pokemontcg.io/test/${serial}.png`,
  };
}

describe("BattleBoard complete public-card view", () => {
  it("renders eight bench slots, own hand, both discards and the stadium without opponent hand identities", () => {
    const frame = battleFrameSchema.parse({
      frameId: 1,
      turn: 4,
      actionCount: 8,
      actingPlayer: 0,
      phase: "main",
      players: [
        {
          name: "自分",
          active: card(0, 1, "Self Active", "active"),
          bench: Array.from({ length: 8 }, (_, index) => card(0, 10 + index, `Bench ${index + 1}`, "bench", index)),
          hand: [card(0, 30, "Visible Hand Card", "hand")],
          handCount: 1,
          deckCount: 35,
          prizeCount: 4,
          discard: [card(0, 40, "Self Discard", "discard")],
        },
        {
          name: "相手",
          active: card(1, 2, "Opponent Active", "active"),
          bench: [],
          hand: [],
          handCount: 6,
          deckCount: 40,
          prizeCount: 5,
          discard: [card(1, 50, "Opponent Discard", "discard")],
        },
      ],
      stadium: card(0, 60, "Area Zero Underdepths", "unknown"),
      events: [],
      decision: null,
      result: null,
    });
    const html = renderToStaticMarkup(<BattleBoard frame={frame} previousFrame={null} onSelect={() => undefined} catalog={new Map()} motionMode="lite" />);
    expect(html).toContain("Bench 8");
    expect(html).toContain("Visible Hand Card");
    expect(html).toContain("Self Discard");
    expect(html).toContain("Opponent Discard");
    expect(html).toContain("Area Zero Underdepths");
    expect(html).toContain("手札 6枚");
    expect(html).not.toContain("Secret Opponent Card");
    expect((html.match(/data-board-marker=\"self-bench\"/g) ?? []).length).toBe(1);
  });
});
