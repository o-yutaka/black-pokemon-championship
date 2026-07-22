import { describe, expect, it } from "vitest";
import { parseLiveSnapshot, toWebSocketUrl } from "./live";

const frame = {
  frameId: 0,
  turn: 1,
  actionCount: 0,
  actingPlayer: 0,
  phase: "main",
  players: [
    { name: "A", active: null, bench: [], hand: [], handCount: 0, deckCount: 60, prizeCount: 6, discard: [], supporterPlayed: false, retreated: false },
    { name: "B", active: null, bench: [], hand: [], handCount: 0, deckCount: 60, prizeCount: 6, discard: [], supporterPlayed: false, retreated: false },
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
  });

  it("ignores non-snapshot messages", () => {
    expect(parseLiveSnapshot({ type: "pong" })).toBeNull();
  });
});
