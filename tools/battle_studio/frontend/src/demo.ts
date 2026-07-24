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
        decisionId: "184",
        goal: "2T Dragapult Attack",
        chosen: "Drakloak Ability",
        confidence: 0.91,
        expectedWinRate: 0.843,
        elapsedMs: 147,
        priority: ["Energy", "Drakloak", "Candy", "Attack"],
        scores: { policy: 42, ability: 18, prizeRoute: 12, wastePenalty: 0, total: 72 },
        candidates: [
          { label: "Ability", score: 81, selected: true, kind: "ABILITY", cardId: 120, serial: 1002 },
          { label: "Energy", score: 73, selected: false },
          { label: "Attack", score: 61, selected: false },
          { label: "Switch", score: 14, selected: false, reason: "RESOURCE_LOOP" }
        ],
        selectedAction: { optionIndex: 3, kind: "ABILITY", cardId: 120, serial: 1002, effectSource: "Drakloak", label: "Drakloak Ability" },
        searchTree: {
          id: "root", label: "Root", status: "root", ev: 81, visits: 301, mean: 76.4, worst: 44, best: 91, reason: null,
          children: [
            { id: "attack", label: "Attack", status: "expanded", ev: 61, visits: 71, mean: 60.8, worst: 42, best: 79, reason: null, children: [] },
            { id: "energy", label: "Energy", status: "expanded", ev: 73, visits: 84, mean: 72.5, worst: 55, best: 86, reason: null, children: [] },
            { id: "switch", label: "Switch", status: "pruned", ev: 14, visits: 0, mean: null, worst: null, best: null, reason: "RESOURCE_LOOP", children: [] },
            { id: "ability", label: "Ability", status: "selected", ev: 81, visits: 146, mean: 82.4, worst: 61, best: 89, reason: null, children: [] }
          ]
        },
        rejectedBranches: [{
          label: "Switch",
          reason: "RESOURCE_LOOP",
          evidence: ["Retreat Lost", "Prize 0"],
          metrics: { "Energy Tempo": -12, "Future Attack": "-18%" },
          killedBy: ["CLOCK_V3", "ENERGY_POLICY", "DRAGAPULT_ROUTE"]
        }],
        policyTrace: [
          { name: "EnergyPolicy", status: "PASS", score: 16, reason: "Future Damage" },
          { name: "DragapultPolicy", status: "PASS", score: 21, reason: "2T attack route" },
          { name: "Clock", status: "PASS", score: 8, reason: "Attack window maintained" },
          { name: "BossPolicy", status: "FAIL", score: -14, reason: "Prize expectation decreased" }
        ],
        boardAnalysis: { total: 81, components: { Energy: 23, Tempo: 18, Bench: 15, Damage: 11, Draw: 9, Future: 5 }, threatMap: { Garchomp: 10, Dragapult: 6, Crustle: 2 } },
        route: { name: "Win Route", steps: ["Attack x2", "Prize2", "Boss", "Prize2", "Attack", "Game"], currentStep: 3 },
        prizePlanner: { neededAttacks: 2, expectedAttacks: 1.8, risk: 0.12, alternatives: [{ label: "Current", score: 84, selected: true }, { label: "Boss", score: 79, selected: false }, { label: "Bench", score: 81, selected: false }] },
        heatmap: { Attach: 100, Candy: 80, Ability: 96, Boss: 50, Switch: 10 },
        policyBattle: { Clock: 74, Energy: 83, Attack: 92, Judge: 88 },
        counterfactuals: [{ label: "もしSwitchしていたら", baselineWinRate: 0.84, alternativeWinRate: 0.62, reason: "Tempo Loss" }],
        causalityGraph: { nodes: ["Rare Candy", "Attack Enabled", "Prize", "Boss", "Win"], edges: [{ from: "Rare Candy", to: "Attack Enabled" }, { from: "Attack Enabled", to: "Prize" }, { from: "Prize", to: "Boss" }, { from: "Boss", to: "Win" }] },
        hiddenBelief: { "Enemy Rare Candy": 0.32, Boss: 0.81, Energy: 0.96 },
        decisionDiff: { previous: "Switch", current: "Attach", why: "Clock V3", delta: 17 },
        truthLedger: { Truth: "PASS", Evidence: 5, Policy: "Dragapult", Engine: "PASS", Search: "PASS", Confidence: "91%", Seed: 184 },
        boardDiff: ["P1 手札: 5→6 (+1)"],
        warnings: [],
        alternatives: []
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
