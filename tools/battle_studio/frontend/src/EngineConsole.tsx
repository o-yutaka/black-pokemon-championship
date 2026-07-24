import { useEffect, useMemo, useRef, useState } from "react";
import { uploadKaggleBundle, type BundleInfo } from "./bundle";
import { detectIosBridgeClient, getInitialBridgeUrl, persistBridgeUrl } from "./bridge-url";
import type { LiveStatus } from "./live";
import { liveStatusJa } from "./locale";
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

const DESKTOP_START_COMMAND = "cd ~/black-pokemon-championship && git pull && bash tools/battle_studio/start_bridge.sh";
const IPHONE_START_COMMAND = `${DESKTOP_START_COMMAND} --iphone`;

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
        <div><span className="eyebrow">{required ? "必須" : "任意"}</span><h3>{title}</h3><p>{hint}</p></div>
        <span className={`bundle-state ${info ? "ok" : "empty"}`}>{info ? "検証済み" : "未選択"}</span>
      </div>
      {!info ? (
        <button className="bundle-drop" type="button" onClick={onPick} disabled={busy}>
          <strong>{busy ? "検証中…" : "Kaggle Bundleを選択"}</strong>
          <span>iPhoneの「ファイル」App対応 · .tar.gz / .tgz</span>
        </button>
      ) : (
        <>
          <dl className="bundle-meta">
            <div><dt>Bundle ID</dt><dd>{info.bundleId}</dd></div>
            <div><dt>Archive SHA</dt><dd title={info.archiveSha256}>{shortSha(info.archiveSha256)}</dd></div>
            <div><dt>Engine SHA</dt><dd title={info.engineSha256}>{shortSha(info.engineSha256)}</dd></div>
            <div><dt>デッキ</dt><dd>{info.deckCount}枚 / {summary.length}種類</dd></div>
            <div><dt>構成ファイル</dt><dd>{info.members.length}件</dd></div>
          </dl>
          <div className="deck-preview" aria-label={`${title}のデッキ内容`}>
            {summary.slice(0, 18).map(({ cardId, count }) => <span key={cardId}><b>{count}×</b> #{cardId}</span>)}
            {summary.length > 18 && <span>ほか{summary.length - 18}種類</span>}
          </div>
          <div className="bundle-actions"><button type="button" onClick={onPick} disabled={busy}>差し替え</button><button type="button" onClick={onClear} disabled={busy}>解除</button></div>
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
  const isIos = useMemo(detectIosBridgeClient, []);
  const defaultBridgeUrl = useMemo(getInitialBridgeUrl, []);
  const [bridgeUrl, setBridgeUrl] = useState(defaultBridgeUrl);
  const [bridgeState, setBridgeState] = useState<BridgeState>("offline");
  const [checkingBridge, setCheckingBridge] = useState(false);
  const [playerBundle, setPlayerBundle] = useState<BundleInfo | null>(null);
  const [opponentBundle, setOpponentBundle] = useState<BundleInfo | null>(null);
  const [uploadRole, setUploadRole] = useState<BundleRole | null>(null);
  const playerBundleRef = useRef<HTMLInputElement>(null);
  const opponentBundleRef = useRef<HTMLInputElement>(null);

  const normalizedBridgeUrl = (): string => {
    const value = bridgeUrl.trim();
    if (!value) throw new Error("Bridge URLを入力してください");
    return persistBridgeUrl(value);
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
      if (mixedContentRisk) throw new Error("公開サイトからPC内Bridgeへの通信はブラウザに遮断されます。「Bridge画面を直接開く」を押してください。");
      const response = await fetch(new URL("/api/health", normalizedBridgeUrl()), { cache: "no-store" });
      if (!response.ok) throw new Error(`Bridgeの状態確認に失敗しました（HTTP ${response.status}）`);
      const value = await response.json() as { ok?: boolean; officialCabt?: boolean };
      if (!value.ok) throw new Error("Bridgeが正常状態を返しませんでした");
      setBridgeState(value.officialCabt ? "ready" : "runner-missing");
    } catch (caught) {
      setBridgeState("offline");
      const raw = caught instanceof Error ? caught.message : "Bridgeの確認に失敗しました";
      onError(raw === "Failed to fetch" ? "Bridgeが起動していません。下の1行コマンドをWSL2で実行してください。" : raw);
    } finally {
      setCheckingBridge(false);
    }
  };

  useEffect(() => {
    if (!mixedContentRisk) void checkBridge();
  }, []);

  const uploadBundle = async (role: BundleRole, file: File | undefined) => {
    if (!file) return;
    setUploadRole(role);
    onError(null);
    try {
      const info = await uploadKaggleBundle(normalizedBridgeUrl(), file);
      if (role === "player") setPlayerBundle(info); else setOpponentBundle(info);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Bundleのアップロードに失敗しました");
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
      onError(caught instanceof Error ? caught.message : "Bridge URLが正しくありません");
    }
  };

  const runnerReady = bridgeState === "ready";
  const startCommand = isIos ? IPHONE_START_COMMAND : DESKTOP_START_COMMAND;
  return (
    <section className="engine-console" aria-label="公式エンジン接続画面">
      <input ref={playerBundleRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip,application/x-gzip" onChange={(event) => void uploadBundle("player", event.target.files?.[0])} />
      <input ref={opponentBundleRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip,application/x-gzip" onChange={(event) => void uploadBundle("opponent", event.target.files?.[0])} />
      <div className="engine-console-head"><div><span className="eyebrow">公式エンジンBRIDGE</span><h2>Kaggle Agent操作</h2><p>提出Bundleを検証し、WSL2の公式エンジンへ接続して盤面を反映する。</p></div><span className={`engine-status ${bridgeState}`}>{liveStatusJa(bridgeState)}</span></div>
      <div className="bridge-launch"><strong>WSL2起動コマンド</strong><code>{startCommand}</code><span>{isIos ? "管理者確認後、表示されたPC-IPのURLをiPhone Safariで開く。" : "実行するとBridgeを起動し、ローカル画面を自動で開く。"}</span></div>
      <div className="bridge-row"><label>Bridge URL<input value={bridgeUrl} onChange={(event) => setBridgeUrl(event.target.value)} placeholder={isIos ? "http://192.168.x.x:8000" : "http://127.0.0.1:8000"} spellCheck={false} autoCapitalize="none" autoCorrect="off" inputMode="url" /></label><button type="button" onClick={() => void checkBridge()} disabled={checkingBridge}>{checkingBridge ? "確認中…" : "接続確認"}</button>{bridgeLink && <a href={bridgeLink}>Bridge画面を直接開く</a>}</div>
      {mixedContentRisk && <div className="engine-warning">この公開ページはHTTPSのため、PC内のHTTP Bridgeへ直接通信できない。「Bridge画面を直接開く」でローカル画面へ切り替える。</div>}
      {bridgeState === "runner-missing" && <div className="engine-warning">Bridgeは接続済み。外部Runnerを使わない場合は、下の「ローカル公式Runtime」へEngine ZIPまたはlibcg.soを登録する。</div>}
      {bridgeState === "offline" && bridgeUrl && <div className="engine-warning">Bridge未接続。上の1行コマンドをWSL2で実行してから、Bridge画面を直接開いてください。</div>}
      <div className="bundle-grid"><BundleSlot title="プレイヤー1 / 自分" hint="外部Runner用Kaggle Agent" info={playerBundle} busy={uploadRole === "player"} required onPick={() => playerBundleRef.current?.click()} onClear={() => setPlayerBundle(null)} /><BundleSlot title="プレイヤー2 / 相手" hint="外部Runner側の対戦相手" info={opponentBundle} busy={uploadRole === "opponent"} onPick={() => opponentBundleRef.current?.click()} onClear={() => setOpponentBundle(null)} /></div>
      <div className="engine-runbar"><div className="engine-live-meta"><span className={`live-dot ${liveStatus}`}></span><strong>{liveEngine ?? "エンジン未接続"}</strong><span>{liveStatusJa(liveStatus)}</span><span>選択肢 {legalSelectionCount}件</span></div><div className="engine-run-actions"><button type="button" onClick={() => start("emulator")} disabled={!bridgeUrl || liveStatus === "connecting" || liveStatus === "connected"}>エミュレーター</button><button className="primary" type="button" onClick={() => start("official")} disabled={!playerBundle || !runnerReady || liveStatus === "connecting" || liveStatus === "connected"}>外部Runner開始</button><button type="button" onClick={onStep} disabled={liveStatus !== "connected" || legalSelectionCount === 0}>1手進める</button><button type="button" onClick={onDisconnect} disabled={liveStatus === "disconnected"}>切断</button></div></div>
    </section>
  );
}
