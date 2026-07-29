import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { BattleBoard } from "./BattleBoard";
import { battleFrameSchema, type CardInstance } from "./types";

function card(playerIndex: 0 | 1, serial: number, name: string, zone: CardInstance["zone"]): CardInstance {
  return {
    playerIndex,
    serial,
    cardId: serial + 1000,
    name,
    zone,
    slot: 0,
    hp: zone === "active" || zone === "bench" ? 100 : null,
    maxHp: zone === "active" || zone === "bench" ? 100 : null,
    damage: 0,
    energies: [],
    tools: [],
    status: [],
    evolution: [],
    imageUrl: null,
  };
}

function frame(simulator: boolean) {
  return battleFrameSchema.parse({
    frameId: simulator ? 2 : 1,
    turn: 1,
    actionCount: 0,
    actingPlayer: 0,
    phase: "main",
    players: [
      {
        name: "自分",
        active: card(0, 1, "Self Active", "active"),
        bench: [],
        hand: [card(0, 2, "Self Hand", "hand")],
        handCount: 1,
        deck: simulator ? [card(0, 3, "Self Deck Secret", "deck")] : [],
        deckCount: 40,
        prize: simulator ? [card(0, 4, "Self Prize Secret", "prize")] : [],
        prizeCount: 6,
        discard: [],
      },
      {
        name: "相手",
        active: card(1, 11, "Opponent Active", "active"),
        bench: [],
        hand: simulator ? [card(1, 12, "Opponent Hand Secret", "hand")] : [],
        handCount: 1,
        deck: simulator ? [card(1, 13, "Opponent Deck Secret", "deck")] : [],
        deckCount: 39,
        prize: simulator ? [card(1, 14, "Opponent Prize Secret", "prize")] : [],
        prizeCount: 5,
        discard: [],
      },
    ],
    stadium: null,
    events: [],
    decision: null,
    result: null,
  });
}

function render(simulator: boolean): string {
  return renderToStaticMarkup(
    <BattleBoard
      frame={frame(simulator)}
      previousFrame={null}
      onSelect={() => undefined}
      catalog={new Map()}
      motionMode="lite"
    />,
  );
}

describe("simulator card visibility", () => {
  it("keeps hidden zones face-down in player view", () => {
    const html = render(false);
    expect(html).toContain("手札 1枚");
    expect(html).toContain("山札 39枚");
    expect(html).toContain("サイド 5枚");
    expect(html).not.toContain("Opponent Hand Secret");
    expect(html).not.toContain("Opponent Deck Secret");
    expect(html).not.toContain("Opponent Prize Secret");
    expect(html).not.toContain("Self Deck Secret");
    expect(html).not.toContain("Self Prize Secret");
  });

  it("renders both hands decks and prizes face-up in simulator view", () => {
    const html = render(true);
    expect(html).toContain("Opponent Hand Secret");
    expect(html).toContain("Opponent Deck Secret");
    expect(html).toContain("Opponent Prize Secret");
    expect(html).toContain("Self Deck Secret");
    expect(html).toContain("Self Prize Secret");
    expect(html).toContain('data-board-marker="opponent-zones-deck"');
    expect(html).toContain('data-board-marker="opponent-zones-prize"');
    expect(html).toContain('data-board-marker="self-zones-deck"');
    expect(html).toContain('data-board-marker="self-zones-prize"');
  });
});
