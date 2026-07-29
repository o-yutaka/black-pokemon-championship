import { describe, expect, it } from "vitest";
import { parseLiveSnapshot, toWebSocketUrl } from "./live";

const frame = {
  frameId: 0,
  turn: 1,
  actionCount: 0,
  actingPlayer: 0,
  phase: "main",
  players: [
    { name: "A", active: null, bench: [], hand: [], handCount: 0, deck: [], deckCount: 60, prize: [], prizeCount: 6, discard: [], supporterPlayed: false, retreated: false },
    { name: "B", active: null, bench: [], hand: [], handCount: 0, deck: [], deckCount: 60, prize: [], prizeCount: 6, discard: [], supporterPlayed: false, retreated: false },
  ],
  stadium: null,
  events: [],
  decision: null,
  result: null,
};

describe("live transport", () => {
  it("converts HTTP origins to WebSocket URLs", () => {
    expect(toWebSocketUrl("http://127.0.0.1:8000", "/ws/battle/abc")).toBe("ws://127.0.0.1:8000/ws/battle/abc");
    expect(toWebSocketUrl("https://example.test/app", "/ws/battle/abc")).toBe("wss://example.test/ws/battle/abc");
  });

  it("validates authoritative snapshot messages", () => {
    const parsed = parseLiveSnapshot({ type: "snapshot", sessionId: "abc", engine: "emulator", frame, legalSelections: [[0]] });
    expect(parsed?.frame.frameId).toBe(0);
    expect(parsed?.legalSelections).toEqual([[0]]);
    expect(parsed?.controls.canAdvance).toBe(true);
    expect(parsed?.controls.simulatorAvailable).toBe(false);
    expect(parsed?.controls.viewMode).toBe("player");
    expect(parsed?.publicProtocol).toBeNull();
  });

  it("accepts opaque official controls without raw selections", () => {
    const parsed = parseLiveSnapshot({
      type: "snapshot",
      sessionId: "official-1",
      engine: "official-battle",
      publicProtocol: "1.1",
      hiddenInformationPolicy: "player_view",
      frame,
      controls: { canAdvance: true, simulatorAvailable: true, viewMode: "player" },
      cardCatalog: [{ id: 4321, name: "Dragapult ex", number: "130", expansion: "Test", sourceLink: "https://example.test/card" }],
    });
    expect(parsed?.legalSelections).toEqual([]);
    expect(parsed?.controls.canAdvance).toBe(true);
    expect(parsed?.controls.simulatorAvailable).toBe(true);
    expect(parsed?.controls.viewMode).toBe("player");
    expect(parsed?.hiddenInformationPolicy).toBe("player_view");
    expect(parsed?.cardCatalog[0].id).toBe(4321);
  });

  it("accepts an explicit simulator-full snapshot", () => {
    const simulatorFrame = structuredClone(frame);
    simulatorFrame.players[1].hand = [{
      playerIndex: 1,
      serial: 9001,
      cardId: 5555,
      name: "Opponent Secret",
      zone: "hand",
      slot: 0,
      hp: null,
      maxHp: null,
      damage: 0,
      energies: [],
      tools: [],
      status: [],
      evolution: [],
      imageUrl: null,
    }];
    simulatorFrame.players[1].handCount = 1;
    const parsed = parseLiveSnapshot({
      type: "snapshot",
      sessionId: "official-1",
      engine: "official-battle",
      publicProtocol: "1.1",
      hiddenInformationPolicy: "simulator_full",
      frame: simulatorFrame,
      controls: { canAdvance: true, simulatorAvailable: true, viewMode: "simulator" },
      cardCatalog: [{ id: 5555, name: "Opponent Secret", number: "1", expansion: "Test", sourceLink: "" }],
    });
    expect(parsed?.controls.viewMode).toBe("simulator");
    expect(parsed?.hiddenInformationPolicy).toBe("simulator_full");
    expect(parsed?.frame.players[1].hand[0].name).toBe("Opponent Secret");
  });

  it("ignores non-snapshot messages", () => {
    expect(parseLiveSnapshot({ type: "pong" })).toBeNull();
  });
});
