import { useEffect, useState } from "react";
import { getInitialBridgeUrl } from "./bridge-url";
import { runtimeBadgeLabel, shortHead, type BridgeHealth } from "./runtime-health";
import "./runtime-truth.css";

export function RuntimeTruthBadge() {
  const [health, setHealth] = useState<BridgeHealth | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      try {
        const response = await fetch(new URL("/api/health", getInitialBridgeUrl()), { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json() as BridgeHealth;
        if (!cancelled) { setHealth(payload); setFailed(false); }
      } catch {
        if (!cancelled) { setHealth(null); setFailed(true); }
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 10_000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, []);

  const label = failed ? "Bridge未確認" : runtimeBadgeLabel(health);
  const tone = failed || !health?.capabilities.officialSessionStartAvailable
    ? "warn"
    : health.runtime.frontendBuild.matchesRuntimeWorktree
      ? "ok"
      : "stale";

  return (
    <details className={`runtime-truth tone-${tone}`}>
      <summary>{label}</summary>
      <div className="runtime-truth-popover">
        {!health ? <p>Bridgeのhealthを取得できません。</p> : <>
          <strong>{health.runtime.git.branch || "detached"} @ {shortHead(health.runtime.git.head)}</strong>
          <span>worktree: {health.runtime.git.dirty === null ? "unknown" : health.runtime.git.dirty ? `dirty (${health.runtime.git.dirtyEntryCount})` : "clean"}</span>
          <span>build: {health.runtime.frontendBuild.provenanceKnown ? `${health.runtime.frontendBuild.gitBranch || "detached"} @ ${shortHead(health.runtime.frontendBuild.gitHead)}` : "provenance unknown"}</span>
          <span>build一致: {health.runtime.frontendBuild.matchesRuntimeWorktree ? "YES" : "NO"}</span>
          <span>公式Process Runner: {health.capabilities.officialProcessRunnerAvailable ? "利用可" : "なし"}</span>
          <span>Native公式Engine: {health.capabilities.nativeOfficialEngineCount}</span>
          <span>稼働中: 公式 {health.activeSessions.officialProcess + health.activeSessions.officialNative} / emulator {health.activeSessions.emulator}</span>
          {health.warnings.length > 0 && <code>{health.warnings.join(" · ")}</code>}
        </>}
      </div>
    </details>
  );
}
