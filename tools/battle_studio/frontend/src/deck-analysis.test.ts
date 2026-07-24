import { describe, expect, it } from "vitest";
import { buildBundleGate, canonicalDeck, deckDiff, parseAnalysisReport, staticSynergyWarnings, type AnalysisCatalogCard } from "./deck-analysis";

const catalog = new Map<number, AnalysisCatalogCard>([
  [1, { id: 1, name: "Basic A", kind: "Pokemon", stage: "Basic", previous: "", basicEnergy: false, basicPokemon: true, ace: false }],
  [2, { id: 2, name: "Trainer B", kind: "Trainer", stage: "Item", previous: "", basicEnergy: false, basicPokemon: false, ace: false }],
  [3, { id: 3, name: "Psychic Energy", kind: "Energy", stage: "Basic Energy", previous: "", basicEnergy: true, basicPokemon: false, ace: false }],
]);

describe("BLACK deck analysis", () => {
  it("normalizes deck identity independently of card order", () => {
    expect(canonicalDeck([2, 1, 1, 3])).toBe(canonicalDeck([1, 3, 2, 1]));
    expect(canonicalDeck([2, 1, 1, 3])).toBe("1,2\n2,1\n3,1\n");
  });

  it("shows exact card-id deltas", () => {
    expect(deckDiff([1, 1, 2], [1, 2, 3], catalog)).toEqual([
      { cardId: 1, name: "Basic A", delta: -1 },
      { cardId: 3, name: "Psychic Energy", delta: 1 },
    ]);
  });

  it("parses evidence without inventing missing results", () => {
    const report = parseAnalysisReport({
      schemaVersion: "1.0",
      intent: { winCondition: "Attack", idealTurns: ["T1 setup"], aceReason: "route", lossConditions: ["brick"], invariants: ["energy 8+"] },
      candidate: { name: "Candidate", matchups: [{ name: "Mirror", wins: 6, losses: 4 }] },
      evaluation: { evaluationId: "eval-1", evaluatedAt: "2026-07-25", method: "official", engineErrors: 0, timeouts: 0 },
    });
    expect(report.candidate?.matchups[0].wins).toBe(6);
    expect(report.current).toBeUndefined();
    expect(() => parseAnalysisReport({ schemaVersion: "2.0" })).toThrow(/1.0/);
  });

  it("keeps static warnings separate from measured evidence", () => {
    const warnings = staticSynergyWarnings([1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3], catalog, {
      schemaVersion: "1.0",
      synergy: [{ severity: "warning", title: "条件不安定", detail: "達成率58%", metric: "174/300" }],
    });
    expect(warnings.some((item) => item.source === "static" && item.title === "たね率が低い")).toBe(true);
    expect(warnings.some((item) => item.source === "evaluation" && item.detail.includes("174/300"))).toBe(true);
  });

  it("blocks promotion while evidence is missing or stale", () => {
    const gates = buildBundleGate({
      total: 60,
      validationOk: true,
      hasBasic: true,
      aceOk: true,
      bundleLoaded: true,
      currentDeckSha: "a".repeat(64),
      context: { report: null, reportSource: null, policySha: "b".repeat(64), freezeSha: null, engineSha: "c".repeat(64), bundleSha: "d".repeat(64), bundledEngineSha: null },
      report: { schemaVersion: "1.0", candidate: { name: "old", deckSha: "e".repeat(64), matchups: [] } },
    });
    expect(gates.find((item) => item.id === "report-hash")?.status).toBe("fail");
    expect(gates.find((item) => item.id === "smoke")?.status).toBe("pending");
    expect(gates.every((item) => item.status === "pass")).toBe(false);
  });
});
