import type { LiveStatus } from "./live";

export type BridgeHealth = {
  ok: boolean;
  healthSchemaVersion: string;
  capabilities: {
    emulatorAvailable: boolean;
    officialProcessRunnerAvailable: boolean;
    nativeOfficialEngineCount: number;
    officialSessionStartAvailable: boolean;
    simulatorViewAllowed: boolean;
    cardCatalogAvailable: boolean;
    publicViewProtocol: string;
  };
  activeSessions: {
    total: number;
    emulator: number;
    officialProcess: number;
    officialNative: number;
    unknown: number;
  };
  runtime: {
    pid: number;
    cwd: string;
    git: {
      repoRoot: string;
      branch: string | null;
      head: string | null;
      dirty: boolean | null;
      dirtyEntryCount: number | null;
    };
    frontendBuild: {
      exists: boolean;
      indexExists: boolean;
      indexSha256: string | null;
      builtAt: string | null;
      gitHead: string | null;
      gitBranch: string | null;
      gitDirty: boolean | null;
      provenanceKnown: boolean;
      matchesRuntimeWorktree: boolean;
    };
  };
  warnings: string[];
};

export function liveSurfaceLabel(liveStatus: LiveStatus, liveEngine: string | null, replaySource: string): string {
  if (liveStatus === "connected") {
    return liveEngine === "official-battle" ? "公式エンジン実戦" : "エミュレーター";
  }
  return replaySource === "cabt" ? "公式Replay" : "Replayビュー";
}

export function runtimeBadgeLabel(health: BridgeHealth | null): string {
  if (!health) return "Bridge確認中";
  if (!health.capabilities.officialSessionStartAvailable) return "公式Runtime未接続";
  if (!health.runtime.frontendBuild.provenanceKnown) return "公式Runtime可・build不明";
  if (!health.runtime.frontendBuild.matchesRuntimeWorktree) return "build不一致";
  return "公式Runtime準備可";
}

export function shortHead(value: string | null): string {
  return value ? value.slice(0, 12) : "unknown";
}
