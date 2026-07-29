import { describe, expect, it } from "vitest";
import { analyzeReplayFailure, generateReplayChangeCandidates, upsertReplayFailureHistory, type ReplayCatalogCard } from "./replay-failure";
import type { BattleFrame, BattleReplay } from "./types";

function player(overrides: Partial<BattleFrame["players"][number]> = {}): BattleFrame["players"][number] {
  return {
    name: "P",
    active: null,
    bench: [],
    hand: [],
    handCount: 5,
    deck: [],
    deckCount: 40,
    prize: [],
    prizeCount: 6,
    discard: [],
    supporterPlayed: false,
    retreated: false,
    ...overrides,
  };
}

function card(serial: number, energies: string[] = []) {
  return {
    playerIndex: 0,
    serial,
    cardId: 10 + serial,
    name: `Card ${serial}`,
    zone: "active" as const,
    slot: null,
    hp: 100,
    maxHp: 100,
    damage: 0,
    energies,
    tools: [],
    status: [],
    evolution: [],
    imageUrl: null,
  };
}

function frame(frameId: number, turn: number, p0: Partial<BattleFrame["players"][number]>, p1: Partial<BattleFrame["players"][number]>, result: string | null = null): BattleFrame {
  return {
    frameId,
    turn,
    actionCount: frameId,
    actingPlayer: 0,
    phase: "main",
    players: [player(p0), player(p1)],
    stadium: null,
    events: [],
    decision: null,
    result,
  };
}

function replay(frames: BattleFrame[], replayId = "r1"): BattleReplay {
  return { schemaVersion: "1.0", replayId, createdAt: "2026-07-25T00:00:00Z", source: "kaggle", hiddenInformationPolicy: "spectator", frames };
}

const catalog: ReplayCatalogCard[] = [
  { id: 1, name: "Basic A", kind: "Pokemon", stage: "Basic", rule: "", moves: [], basicEnergy: false, basicPokemon: true },
  { id: 2, name: "Psychic Energy", kind: "Energy", stage: "", rule: "", moves: [], basicEnergy: true, basicPokemon: false },
  { id: 3, name: "Night Stretcher", kind: "Item", stage: "", rule: "Put a Pokemon from discard into your hand", moves: [], basicEnergy: false, basicPokemon: false },
];

describe("official replay failure analysis", () => {
  it("fails closed while the replay is not terminal", () => {
    const report = analyzeReplayFailure(replay([frame(0, 1, { active: card(1) }, { active: card(2) })]));
    expect(report.outcome).toBe("in_progress");
    expect(report.findings).toEqual([]);
  });

  it("classifies only a confirmed loss and preserves frame evidence", () => {
    const report = analyzeReplayFailure(replay([
      frame(0, 1, { active: card(1), handCount: 2 }, { active: card(2) }),
      frame(1, 2, { active: card(1), handCount: 1 }, { active: card(2), prizeCount: 2 }),
      frame(2, 4, { active: null, bench: [], handCount: 1, deckCount: 1, prizeCount: 5, discard: Array.from({ length: 11 }, (_, index) => card(20 + index)) }, { active: card(2), prizeCount: 0 }),
    ]));
    expect(report.outcome).toBe("loss");
    expect(report.winnerPlayer).toBe(1);
    expect(report.findings.map((item) => item.code)).toEqual(expect.arrayContaining(["SETUP_LOW_BOARD", "ENERGY_DEVELOPMENT_MISS", "ATTACK_DELAY", "HAND_STALL", "BENCH_COLLAPSE", "DECK_EXHAUSTION", "PRIZE_RACE_BEHIND", "HIGH_DISCARD_LOAD"]));
    expect(report.findings.every((item) => item.evidence.every((entry) => Number.isInteger(entry.frameId)))).toBe(true);
  });

  it("does not generate loss findings for a win", () => {
    const report = analyzeReplayFailure(replay([frame(0, 3, { active: card(1), prizeCount: 0 }, { active: card(2), prizeCount: 3 })]));
    expect(report.outcome).toBe("win");
    expect(report.findings).toEqual([]);
  });

  it("generates unverified deck and policy hypotheses from stored losses", () => {
    const loss = analyzeReplayFailure(replay([
      frame(0, 1, { active: card(1), handCount: 2 }, { active: card(2) }),
      frame(1, 2, { active: card(1), handCount: 1 }, { active: card(2) }),
      frame(2, 5, { active: null, bench: [], handCount: 1, deckCount: 1, prizeCount: 5 }, { active: card(2), prizeCount: 0 }),
    ]));
    const candidates = generateReplayChangeCandidates([loss], [1, 1, 1, 2, 2], catalog);
    expect(candidates.length).toBeGreaterThan(0);
    expect(candidates.every((item) => item.status === "unverified")).toBe(true);
    expect(candidates.some((item) => item.options.some((option) => option.cardId === 2))).toBe(true);
    expect(candidates.some((item) => item.kind === "policy")).toBe(true);
  });

  it("deduplicates replay history by replay id", () => {
    const first = analyzeReplayFailure(replay([frame(0, 2, { prizeCount: 5 }, { prizeCount: 0 })], "same"));
    const second = { ...first, analyzedAt: "later" };
    const history = upsertReplayFailureHistory(upsertReplayFailureHistory([], first), second);
    expect(history).toHaveLength(1);
    expect(history[0].analyzedAt).toBe("later");
  });
});
