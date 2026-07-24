import { useEffect, useMemo, useRef, useState } from "react";
import { uploadKaggleBundle, type BundleInfo } from "./bundle";
import type { LiveStatus } from "./live";
import "./engine.css";

type BundleRole = "player" | "opponent";
type BridgeState = "checking" | "ready" | "runner-missing" | "offline";

export type EngineStartRequest = {
  bridgeUrl: string;
  engine: "emulator" | "official" | "official-native";
  bundleId?: string;
  opponentBundleId?: string;
  engineId?: string;
  playerBundleId?: string;
  nativeOpponentBundleId?: string;
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
          <span>iPhoneの「ファイル」App対応 · .tar.gz / .tgz</span>
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

function detectIos(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
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
  const isIos = useMemo(detectIos, []);
  const isBridgeHosted = !window.location.hostname.endsWith("github.io");
  const defaultBridgeUrl = import.meta.env.VITE_LIVE_BASE_URL || (isBridgeHosted ? window.location.origin : localStorage.getItem("black.bridgeUrl") || "http://DESKTOP-C3RJG3V:8000/");
  const [bridgeUrl, setBridgeUrl] = useState(defaultBridgeUrl);
  const [bridgeState, setBridgeState] = useState<BridgeState>(defaultBridgeUrl ? "checking" : "offline");
  const [checkingBridge, setCheckingBridge] = useState(false);
  const [playerBundle, setPlayerBundle] = useState<BundleInfo | null>(null);
  const [opponentBundle, setOpponentBundle] = useState<BundleInfo | null>(null);
  const [uploadRole, setUploadRole] = useState<BundleRole | null>(null);
  const playerBundleRef = useRef<HTMLInputElement>(null);
  const opponentBundleRef = useRef<HTMLInputElement>(null);

  const normalizedBridgeUrl = (): string => {
    const value = bridgeUrl.trim();
    if (!value) throw new Error("Bridge URLを入力してください");
    const normalized = new URL(value).toString();
    localStorage.setItem("black.bridgeUrl", normalized);
    return normalized;
  };

  const bridgeLink = useMemo(() => {
    try { return bridgeUrl.trim() ? new URL(bridgeUrl.trim()).toString() : null; }
    catch { return null; }
  }, [bridgeUrl]);

  const mixedContentRisk = useMemo(() => {
    if (!bridgeLink) return false;
    return window.location.protocol === "https:" && new URL(bridgeLink).protocol === "http:";
  }, [bridgeLink]);

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

  useEffect(() => { if (defaultBridgeUrl) void checkBridge(); }, []);

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
      onStart({ bridgeUrl: normalizedBridgeUrl(), engine, bundleId: engine === "official" ? playerBundle?.bundleId : undefined, opponentBundleId: engine === "official" ? opponentBundle?.bundleId : undefined });
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Invalid Bridge URL");
    }
  };

  const runnerReady = bridgeState === "ready";
  return (
    <section className="engine-console" aria-label="Official engine console">
      <input ref={playerBundleRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip,application/x-gzip" onChange={(event) => void uploadBundle("player", event.target.files?.[0])} />
      <input ref={opponentBundleRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip,application/x-gzip" onChange={(event) => void uploadBundle("opponent", event.target.files?.[0])} />
      <div className="engine-console-head"><div><span className="eyebrow">OFFICIAL ENGINE BRIDGE</span><h2>Kaggle Agent Console</h2><p>提出Bundleを検証し、WSL2の公式エンジンへ接続して盤面をこの画面へ反映する。</p></div><span className={`engine-status ${bridgeState}`}>{bridgeState.replace("-", " ").toUpperCase()}</span></div>
      {isIos && <div className="iphone-mode"><div><strong>iPhone Mode</strong><span>PCと同じWi‑Fiで、WSL2 Bridgeが表示した <code>http://PC-IP:8000/</code> をSafariで直接開く。</span></div>{bridgeLink && <a href={bridgeLink}>Bridge UIを開く</a>}</div>}
      <div className="bridge-row"><label>Bridge URL<input value={bridgeUrl} onChange={(event) => setBridgeUrl(event.target.value)} placeholder={isIos ? "http://192.168.x.x:8000" : "http://127.0.0.1:8000"} spellCheck={false} autoCapitalize="none" autoCorrect="off" inputMode="url" /></label><button type="button" onClick={() => void checkBridge()} disabled={checkingBridge}>{checkingBridge ? "確認中…" : "接続確認"}</button></div>
      {mixedContentRisk && <div className="engine-warning">GitHub Pages（HTTPS）からPCのHTTP Bridgeへ直接通信できない場合がある。上の「Bridge UIを開く」で同一オリジン表示に切り替える。</div>}
      {bridgeState === "runner-missing" && <div className="engine-warning">外部Runnerは未設定。下のLOCAL OFFICIAL RUNTIMEへEngine ZIPまたはlibcg.soを登録すれば直接対戦できる。</div>}
      {bridgeState === "offline" && bridgeUrl && <div className="engine-warning">Bridgeへ接続できない。WSL2側でBridgeを起動し、同じWi‑FiのPC-IPを使用してください。</div>}
      <div className="bundle-grid"><BundleSlot title="PLAYER 1 / 自分" hint="外部Runner用Kaggle Agent" info={playerBundle} busy={uploadRole === "player"} required onPick={() => playerBundleRef.current?.click()} onClear={() => setPlayerBundle(null)} /><BundleSlot title="PLAYER 2 / 相手" hint="外部Runner側の相手" info={opponentBundle} busy={uploadRole === "opponent"} onPick={() => opponentBundleRef.current?.click()} onClear={() => setOpponentBundle(null)} /></div>
      <div className="engine-runbar"><div className="engine-live-meta"><span className={`live-dot ${liveStatus}`}></span><strong>{liveEngine ?? "NO ENGINE"}</strong><span>{liveStatus.toUpperCase()}</span><span>{legalSelectionCount} legal selections</span></div><div className="engine-run-actions"><button type="button" onClick={() => start("emulator")} disabled={!bridgeUrl || liveStatus === "connecting" || liveStatus === "connected"}>Emulator</button><button className="primary" type="button" onClick={() => start("official")} disabled={!playerBundle || !runnerReady || liveStatus === "connecting" || liveStatus === "connected"}>External Runner</button><button type="button" onClick={onStep} disabled={liveStatus !== "connected" || legalSelectionCount === 0}>Live Step</button><button type="button" onClick={onDisconnect} disabled={liveStatus === "disconnected"}>Disconnect</button></div></div>
    </section>
  );
}
