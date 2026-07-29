import { describe, expect, it } from "vitest";
import { liveSurfaceLabel, runtimeBadgeLabel, type BridgeHealth } from "./runtime-health";

const health = (official: boolean, known: boolean, matches: boolean): BridgeHealth => ({
  ok: true,
  healthSchemaVersion: "2.0",
  capabilities: {
    emulatorAvailable: true,
    officialProcessRunnerAvailable: official,
    nativeOfficialEngineCount: 0,
    officialSessionStartAvailable: official,
    simulatorViewAllowed: false,
    cardCatalogAvailable: true,
    publicViewProtocol: "1.1",
  },
  activeSessions: { total: 0, emulator: 0, officialProcess: 0, officialNative: 0, unknown: 0 },
  runtime: {
    pid: 1,
    cwd: "/repo/tools/battle_studio/backend",
    git: { repoRoot: "/repo", branch: "main", head: "a".repeat(40), dirty: false, dirtyEntryCount: 0 },
    frontendBuild: {
      exists: true,
      indexExists: true,
      indexSha256: "b".repeat(64),
      builtAt: "2026-07-30T00:00:00Z",
      gitHead: known ? "a".repeat(40) : null,
      gitBranch: known ? "main" : null,
      gitDirty: known ? false : null,
      provenanceKnown: known,
      matchesRuntimeWorktree: matches,
    },
  },
  warnings: [],
});

describe("runtime truth labels", () => {
  it("never calls an emulator connection official", () => {
    expect(liveSurfaceLabel("connected", "cabt-shape-emulator", "unknown")).toBe("エミュレーター");
    expect(liveSurfaceLabel("connected", "official-battle", "unknown")).toBe("公式エンジン実戦");
    expect(liveSurfaceLabel("disconnected", null, "cabt")).toBe("公式Replay");
  });

  it("separates official capability from build provenance", () => {
    expect(runtimeBadgeLabel(health(false, true, true))).toBe("公式Runtime未接続");
    expect(runtimeBadgeLabel(health(true, false, false))).toBe("公式Runtime可・build不明");
    expect(runtimeBadgeLabel(health(true, true, false))).toBe("build不一致");
    expect(runtimeBadgeLabel(health(true, true, true))).toBe("公式Runtime準備可");
  });
});
