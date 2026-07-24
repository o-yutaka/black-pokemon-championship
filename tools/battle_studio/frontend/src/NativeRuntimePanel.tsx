import { useRef, useState } from "react";
import { persistBridgeUrl } from "./bridge-url";
import type { LiveStatus } from "./live";
import "./native-runtime.css";

type EngineArtifact = { id: string; filename: string; sha256: string; sourceKind: string; compiler?: string | null };
type BundleArtifact = { id: string; filename: string; sha256: string; deckCount: number; uniqueCardIds: number; bundledEngineSha256?: string | null };
type NativeStartRequest = { bridgeUrl: string; engine: "official-native"; engineId: string; playerBundleId: string; nativeOpponentBundleId: string };

type Props = {
  liveStatus: LiveStatus;
  onStart(request: NativeStartRequest): void;
  onError(message: string | null): void;
};

async function responseJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({})) as T & { detail?: string };
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
}

function shortSha(value?: string | null): string {
  return value ? `${value.slice(0, 12)}…` : "—";
}

export function NativeRuntimePanel({ liveStatus, onStart, onError }: Props) {
  const engineRef = useRef<HTMLInputElement>(null);
  const playerRef = useRef<HTMLInputElement>(null);
  const opponentRef = useRef<HTMLInputElement>(null);
  const [engine, setEngine] = useState<EngineArtifact | null>(null);
  const [player, setPlayer] = useState<BundleArtifact | null>(null);
  const [opponent, setOpponent] = useState<BundleArtifact | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const bridgeUrl = (): string => persistBridgeUrl(localStorage.getItem("black.bridgeUrl") || "http://DESKTOP-C3RJG3V:8000/");

  const run = async (label: string, task: () => Promise<void>) => {
    setBusy(label);
    onError(null);
    try { await task(); }
    catch (error) { onError(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(null); }
  };

  const uploadEngine = (file?: File) => file && void run("engine", async () => {
    const body = new FormData();
    body.append("file", file);
    const payload = await responseJson<{ engine: EngineArtifact }>(await fetch(new URL("/api/native/engine", bridgeUrl()), { method: "POST", body }));
    setEngine(payload.engine);
    setPlayer(null);
    setOpponent(null);
  });

  const uploadBundle = (role: "player" | "opponent", file?: File) => file && void run(role, async () => {
    const body = new FormData();
    body.append("file", file);
    const url = new URL("/api/native/bundles", bridgeUrl());
    if (engine) url.searchParams.set("engine_id", engine.id);
    const payload = await responseJson<{ bundle: BundleArtifact }>(await fetch(url, { method: "POST", body }));
    if (role === "player") setPlayer(payload.bundle); else setOpponent(payload.bundle);
  });

  const ready = Boolean(engine && player && opponent && !busy && liveStatus !== "connecting" && liveStatus !== "connected");

  return (
    <section className="native-runtime" aria-label="Local official engine runtime">
      <div className="native-runtime-head">
        <div><span className="eyebrow">LOCAL OFFICIAL RUNTIME</span><h2>Engine ZIP / libcg.so 直結</h2><p>外部Runnerなしで、アップロードした2つのKaggle Agentを同じ公式エンジン上で対戦させる。</p></div>
        <span className={`native-state ${ready ? "ready" : "setup"}`}>{ready ? "READY" : "SETUP"}</span>
      </div>
      <div className="native-grid">
        <article><strong>1. 公式エンジン</strong><p>{engine?.filename || "ptcg_engine ZIP または libcg.so"}</p><small>{engine ? `${engine.sourceKind} · ${shortSha(engine.sha256)}` : "ZIPはWSL2内でC++20ビルド"}</small><button type="button" onClick={() => engineRef.current?.click()} disabled={Boolean(busy)}>{busy === "engine" ? "Building…" : "Upload Engine"}</button></article>
        <article><strong>2. 自分のBundle</strong><p>{player?.filename || ".tar.gz / .tgz"}</p><small>{player ? `${player.deckCount} cards · ${shortSha(player.sha256)}` : "root main.py + deck.csv"}</small><button type="button" onClick={() => playerRef.current?.click()} disabled={!engine || Boolean(busy)}>Upload Player</button></article>
        <article><strong>3. 相手Bundle</strong><p>{opponent?.filename || ".tar.gz / .tgz"}</p><small>{opponent ? `${opponent.deckCount} cards · ${shortSha(opponent.sha256)}` : "別Agentを同じEngineへ接続"}</small><button type="button" onClick={() => opponentRef.current?.click()} disabled={!engine || Boolean(busy)}>Upload Opponent</button></article>
      </div>
      <button className="native-start primary" type="button" disabled={!ready} onClick={() => engine && player && opponent && onStart({ bridgeUrl: bridgeUrl(), engine: "official-native", engineId: engine.id, playerBundleId: player.id, nativeOpponentBundleId: opponent.id })}>Start Official Match</button>
      <input ref={engineRef} className="file-input" type="file" accept=".zip,.so,application/zip,application/octet-stream" onChange={(event) => { uploadEngine(event.target.files?.[0]); event.currentTarget.value = ""; }} />
      <input ref={playerRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip" onChange={(event) => { uploadBundle("player", event.target.files?.[0]); event.currentTarget.value = ""; }} />
      <input ref={opponentRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip" onChange={(event) => { uploadBundle("opponent", event.target.files?.[0]); event.currentTarget.value = ""; }} />
    </section>
  );
}
