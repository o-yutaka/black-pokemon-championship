import type { BattleReplay, CardInstance } from "./types";

const card = (
  playerIndex: 0 | 1,
  serial: number,
  cardId: number,
  name: string,
  zone: CardInstance["zone"],
  slot: number | null,
  hp: number | null,
  maxHp: number | null,
  damage = 0,
  energies: string[] = [],
): CardInstance => ({
  playerIndex,
  serial,
  cardId,
  name,
  zone,
  slot,
  hp,
  maxHp,
  damage,
  energies,
  tools: [],
  status: [],
  evolution: [],
  imageUrl: null,
});

const p0Active = card(0, 1001, 121, "Dragapult ex", "active", 0, 320, 320, 0, ["Psychic", "Fire"]);
const p0BenchA = card(0, 1002, 120, "Drakloak", "bench", 0, 90, 90, 0, ["Psychic"]);
const p0BenchB = card(0, 1003, 133, "Dusknoir", "bench", 1, 160, 160);
const p1Active = card(1, 2001, 900, "Opponent Active", "active", 0, 220, 220, 0, ["Colorless", "Colorless"]);
const p1BenchA = card(1, 2002, 901, "Opponent Bench", "bench", 0, 130, 130);

const player = (name: string, active: CardInstance | null, bench: CardInstance[], handCount: number, deckCount: number, prizeCount: number) => ({
  name,
  active,
  bench,
  hand: [],
  handCount,
  deckCount,
  prizeCount,
  discard: [],
  supporterPlayed: false,
  retreated: false,
});

export const demoReplay: BattleReplay = {
  schemaVersion: "1.0",
  replayId: "black-demo-001",
  createdAt: "2026-07-22T00:00:00Z",
  source: "demo",
  hiddenInformationPolicy: "spectator",
  frames: [
    {
      frameId: 0,
      turn: 6,
      actionCount: 31,
      actingPlayer: 0,
      phase: "main",
      players: [player("BLACK", p0Active, [p0BenchA, p0BenchB], 6, 28, 4), player("Red Team", p1Active, [p1BenchA], 5, 30, 4)],
      stadium: null,
      events: [{ type: "turn", actor: 0, text: "BLACK turn started", cardKey: null }],
      decision: {
        actor: 0,
        goal: "two-turn prize route",
        chosen: "Phantom Dive",
        confidence: 0.82,
        elapsedMs: 147,
        candidates: [
          { label: "Phantom Dive", score: 8.7, selected: true },
          { label: "Boss's Orders", score: 7.2, selected: false },
          { label: "End turn", score: -3.0, selected: false }
        ]
      },
      result: null
    },
    {
      frameId: 1,
      turn: 6,
      actionCount: 32,
      actingPlayer: 0,
      phase: "attack",
      players: [player("BLACK", p0Active, [p0BenchA, p0BenchB], 6, 28, 4), player("Red Team", { ...p1Active, hp: 20, damage: 200 }, [{ ...p1BenchA, hp: 70, damage: 60 }], 5, 30, 4)],
      stadium: null,
      events: [
        { type: "attack", actor: 0, text: "Dragapult ex used Phantom Dive", cardKey: "0:1001" },
        { type: "damage", actor: 0, text: "200 damage to Active; 60 damage counters to Bench", cardKey: "1:2001" }
      ],
      decision: null,
      result: null
    },
    {
      frameId: 2,
      turn: 7,
      actionCount: 33,
      actingPlayer: 1,
      phase: "turn_start",
      players: [player("BLACK", p0Active, [p0BenchA, p0BenchB], 6, 28, 4), player("Red Team", { ...p1Active, hp: 20, damage: 200 }, [{ ...p1BenchA, hp: 70, damage: 60 }], 6, 29, 4)],
      stadium: null,
      events: [{ type: "turn", actor: 1, text: "Red Team turn started", cardKey: null }],
      decision: null,
      result: null
    }
  ]
};
