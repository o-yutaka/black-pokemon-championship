import { useEffect, useRef, useState } from "react";
import { uploadKaggleBundle, type BundleInfo } from "./bundle";
import type { LiveStatus } from "./live";
import "./engine.css";

type BundleRole = "player" | "opponent";
type BridgeState = "checking" | "ready" | "runner-missing" | "offline";

export type EngineStartRequest = {
  bridgeUrl: string;
  engine: "emulator" | "official";
  bundleId?: string;
  opponentBundleId?: string;
};

function shortSha(value: string): string {
  return value.length > 16 ? `${value.slice(0, 12)}…${value.slice(-4)}` : value;
}

function deckSummary(deck: number[]): Array<{ cardId: number; count: number }> {
  const counts = new Map<number, number>();
  deck.forEach((cardId) => counts.set(cardId, (counts.get(cardId) ?? 0) + 1));
  return [...counts.entries()].map(([cardId, count]) => ({ cardId, count })).sort((a, b) => a.cardId - b.cardId);
}

function BundleSlot({ title, hint, info, busy, required, onPick, onClear }: {
  title: string;
  hint: string;
  info: BundleInfo | null;
  busy: boolean;
  required?: boolean;
  onPick: () => void;
  onClear: () => void;
}) {
  const summary = info ? deckSummary(info.deck) : [];
  return (
    <article className={`bundle-slot ${info ? "loaded" : ""}`}>
      <div className="bundle-slot-head">
        <div>
          <span className="eyebrow">{required ? "REQUIRED" : "OPTIONAL"}</span>
          <h3>{title}</h3>
          <p>{hint}</p>
        </div>
        <span className={`bundle-state ${info ? "ok" : "empty"}`}>{info ? "VALID" : "EMPTY"}</span>
      </div>
      {!info ? (
        <button className="bundle-drop" type="button" onClick={onPick} disabled={busy}>
          <strong>{busy ? "検証中…" : "Kaggle Bundleを選択"}</strong>
          <span>.tar.gz / .tgz</span>
        </button>
      ) : (
        <>
          <dl className="bundle-meta">
            <div><dt>Bundle</dt><dd>{info.bundleId}</dd></div>
            <div><dt>Archive SHA</dt><dd title={info.archiveSha256}>{shortSha(info.archiveSha256)}</dd></div>
            <div><dt>Engine SHA</dt><dd title={info.engineSha256}>{shortSha(info.engineSha256)}</dd></div>
            <div><dt>Deck</dt><dd>{info.deckCount} cards / {summary.length} unique</dd></div>
            <div><dt>Manifest</dt><dd>{info.members.length} files</dd></div>
          </dl>
          <div className="deck-preview" aria-label={`${title} deck preview`}>
            {summary.slice(0, 18).map(({ cardId, count }) => <span key={cardId}><b>{count}×</b> #{cardId}</span>)}
            {summary.length > 18 && <span>+{summary.length - 18} types</span>}
          </div>
          <div className="bundle-actions">
            <button type="button" onClick={onPick} disabled={busy}>差し替え</button>
            <button type="button" onClick={onClear} disabled={busy}>解除</button>
          </div>
        </>
      )}
    </article>
  );
}

export function EngineConsole({ liveStatus, liveEngine, legalSelectionCount, onStart, onStep, onDisconnect, onError }: {
  liveStatus: LiveStatus;
  liveEngine: string | null;
  legalSelectionCount: number;
  onStart: (request: EngineStartRequest) => void;
  onStep: () => void;
  onDisconnect: () => void;
  onError: (message: string | null) => void;
}) {
  const defaultBridgeUrl = import.meta.env.VITE_LIVE_BASE_URL || (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" ? window.location.origin : "http://127.0.0.1:8000");
  const [bridgeUrl, setBridgeUrl] = useState(defaultBridgeUrl);
  const [bridgeState, setBridgeState] = useState<BridgeState>("checking");
  const [checkingBridge, setCheckingBridge] = useState(false);
  const [playerBundle, setPlayerBundle] = useState<BundleInfo | null>(null);
  const [opponentBundle, setOpponentBundle] = useState<BundleInfo | null>(null);
  const [uploadRole, setUploadRole] = useState<BundleRole | null>(null);
  const playerBundleRef = useRef<HTMLInputElement>(null);
  const opponentBundleRef = useRef<HTMLInputElement>(null);

  const normalizedBridgeUrl = (): string => {
    const value = bridgeUrl.trim();
    if (!value) throw new Error("Bridge URLを入力してください");
    return new URL(value).toString();
  };

  const checkBridge = async () => {
    setCheckingBridge(true);
    setBridgeState("checking");
    onError(null);
    try {
      const response = await fetch(new URL("/api/health", normalizedBridgeUrl()), { cache: "no-store" });
      if (!response.ok) throw new Error(`Bridge health failed: HTTP ${response.status}`);
      const value = await response.json() as { ok?: boolean; officialCabt?: boolean };
      if (!value.ok) throw new Error("Bridge returned unhealthy status");
      setBridgeState(value.officialCabt ? "ready" : "runner-missing");
    } catch (caught) {
      setBridgeState("offline");
      onError(caught instanceof Error ? caught.message : "Bridge check failed");
    } finally {
      setCheckingBridge(false);
    }
  };

  useEffect(() => { void checkBridge(); }, []);

  const uploadBundle = async (role: BundleRole, file: File | undefined) => {
    if (!file) return;
    setUploadRole(role);
    onError(null);
    try {
      const info = await uploadKaggleBundle(normalizedBridgeUrl(), file);
      if (role === "player") setPlayerBundle(info);
      else setOpponentBundle(info);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Bundle upload failed");
    } finally {
      setUploadRole(null);
      if (role === "player" && playerBundleRef.current) playerBundleRef.current.value = "";
      if (role === "opponent" && opponentBundleRef.current) opponentBundleRef.current.value = "";
    }
  };

  const start = (engine: "emulator" | "official") => {
    try {
      onStart({
        bridgeUrl: normalizedBridgeUrl(),
        engine,
        bundleId: engine === "official" ? playerBundle?.bundleId : undefined,
        opponentBundleId: engine === "official" ? opponentBundle?.bundleId : undefined,
      });
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Invalid Bridge URL");
    }
  };

  const runnerReady = bridgeState === "ready";
  return (
    <section className="engine-console" aria-label="Official engine console">
      <input ref={playerBundleRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip" onChange={(event) => void uploadBundle("player", event.target.files?.[0])} />
      <input ref={opponentBundleRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip" onChange={(event) => void uploadBundle("opponent", event.target.files?.[0])} />

      <div className="engine-console-head">
        <div>
          <span className="eyebrow">OFFICIAL ENGINE BRIDGE</span>
          <h2>Kaggle Agent Console</h2>
          <p>提出Bundleを検証し、WSL2の公式エンジンへ接続して盤面をこの画面へ反映する。</p>
        </div>
        <span className={`engine-status ${bridgeState}`}>{bridgeState.replace("-", " ").toUpperCase()}</span>
      </div>

      <div className="bridge-row">
        <label>Bridge URL<input value={bridgeUrl} onChange={(event) => setBridgeUrl(event.target.value)} spellCheck={false} inputMode="url" /></label>
        <button type="button" onClick={() => void checkBridge()} disabled={checkingBridge}>{checkingBridge ? "確認中…" : "接続確認"}</button>
      </div>

      {bridgeState === "runner-missing" && <div className="engine-warning">Bridgeには接続済み。ただし <code>BLACK_OFFICIAL_RUNNER</code> が未設定のため公式対戦は開始できない。</div>}
      {bridgeState === "offline" && <div className="engine-warning">Bridgeへ接続できない。WSL2側のLive Bridgeを起動し、URLを確認してください。</div>}

      <div className="bundle-grid">
        <BundleSlot title="PLAYER 1 / 自分" hint="Kaggleへ提出する自分側Agent" info={playerBundle} busy={uploadRole === "player"} required onPick={() => playerBundleRef.current?.click()} onClear={() => setPlayerBundle(null)} />
        <BundleSlot title="PLAYER 2 / 相手" hint="未指定ならRunner側の標準相手を使用" info={opponentBundle} busy={uploadRole === "opponent"} onPick={() => opponentBundleRef.current?.click()} onClear={() => setOpponentBundle(null)} />
      </div>

      <div className="engine-runbar">
        <div className="engine-live-meta">
          <span className={`live-dot ${liveStatus}`}></span>
          <strong>{liveEngine ?? "NO ENGINE"}</strong>
          <span>{liveStatus.toUpperCase()}</span>
          <span>{legalSelectionCount} legal selections</span>
        </div>
        <div className="engine-run-actions">
          <button type="button" onClick={() => start("emulator")} disabled={liveStatus === "connecting" || liveStatus === "connected"}>Emulator</button>
          <button className="primary" type="button" onClick={() => start("official")} disabled={!playerBundle || !runnerReady || liveStatus === "connecting" || liveStatus === "connected"}>Official Start</button>
          <button type="button" onClick={onStep} disabled={liveStatus !== "connected" || legalSelectionCount === 0}>Live Step</button>
          <button type="button" onClick={onDisconnect} disabled={liveStatus === "disconnected"}>Disconnect</button>
        </div>
      </div>
    </section>
  );
}
