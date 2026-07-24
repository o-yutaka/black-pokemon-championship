import { describe, expect, it } from "vitest";
import { battleFrameSchema } from "./types";

const player = {
  name: "P1",
  active: null,
  bench: [],
  hand: [],
  handCount: 0,
  deckCount: 60,
  prizeCount: 6,
  discard: [],
  supporterPlayed: false,
  retreated: false,
};

describe("BLACK decision overlay", () => {
  it("parses rich local overlay fields", () => {
    const frame = battleFrameSchema.parse({
      frameId: 1,
      turn: 2,
      actionCount: 8,
      actingPlayer: 0,
      phase: "main",
      players: [player, { ...player, name: "P2" }],
      stadium: null,
      events: [],
      result: null,
      decision: {
        actor: 0,
        goal: "prize_route",
        chosen: "Drakloak Ability",
        confidence: 0.82,
        elapsedMs: 15,
        candidates: [{ label: "Drakloak Ability", score: 72, selected: true }],
        selectedAction: { arrayIndex: 0, optionIndex: 3, kind: "ABILITY", cardId: 123, serial: 7, effectSource: "Drakloak", label: "Ability" },
        scores: { policy: 42, ability: 18, total: 72 },
        flags: { abilityUsed: true, lethal: false },
        warnings: ["警告"],
        boardDiff: ["P1 手札: 5→6 (+1)"],
        scoreSource: "agent",
      },
    });
    expect(frame.decision?.selectedAction?.kind).toBe("ABILITY");
    expect(frame.decision?.scores?.total).toBe(72);
    expect(frame.decision?.flags?.abilityUsed).toBe(true);
    expect(frame.decision?.boardDiff).toEqual(["P1 手札: 5→6 (+1)"]);
  });

  it("keeps old replay decisions compatible", () => {
    const frame = battleFrameSchema.parse({
      frameId: 0,
      turn: 0,
      actionCount: 0,
      actingPlayer: 0,
      players: [player, { ...player, name: "P2" }],
      stadium: null,
      events: [],
      result: null,
      decision: { actor: 0, chosen: "[0]", candidates: [] },
    });
    expect(frame.decision?.warnings).toBeUndefined();
    expect(frame.decision?.selectedAction).toBeUndefined();
  });
});
