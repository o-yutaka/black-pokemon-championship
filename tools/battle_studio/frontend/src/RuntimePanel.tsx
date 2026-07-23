import { useRef, useState } from "react";
import type { LiveStatus } from "./live";
import { uploadBundle, uploadCardCatalog, uploadEngine, type BundleArtifact, type EngineArtifact } from "./studio";

export type OfficialSessionRequest = { engine: "official"; engine_id: string; player_bundle_id: string; opponent_bundle_id: string };
type Props = {
  liveStatus: LiveStatus; onConnectEmulator(): void; onConnectOfficial(request: OfficialSessionRequest): void;
  onDisconnect(): void; onPlayerDeck(deck: number[]): void; onCatalogReady(): void;
};

function shortSha(value: string | null | undefined): string { return value ? `${value.slice(0, 12)}…` : "—"; }

export function RuntimePanel({ liveStatus, onConnectEmulator, onConnectOfficial, onDisconnect, onPlayerDeck, onCatalogReady }: Props) {
  const engineRef = useRef<HTMLInputElement>(null); const playerRef = useRef<HTMLInputElement>(null);
  const opponentRef = useRef<HTMLInputElement>(null); const cardsRef = useRef<HTMLInputElement>(null);
  const [engine, setEngine] = useState<EngineArtifact | null>(null); const [player, setPlayer] = useState<BundleArtifact | null>(null);
  const [opponent, setOpponent] = useState<BundleArtifact | null>(null); const [catalog, setCatalog] = useState("未読込");
  const [busy, setBusy] = useState<string | null>(null); const [error, setError] = useState<string | null>(null);

  async function run(label: string, task: () => Promise<void>) {
    setBusy(label); setError(null);
    try { await task(); } catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); } finally { setBusy(null); }
  }
  const loadEngine = (file?: File) => file && void run("engine", async () => setEngine(await uploadEngine(file)));
  const loadPlayer = (file?: File) => file && void run("player", async () => { const result = await uploadBundle(file, engine?.id); setPlayer(result.bundle); onPlayerDeck(result.deck); });
  const loadOpponent = (file?: File) => file && void run("opponent", async () => setOpponent((await uploadBundle(file, engine?.id)).bundle));
  const loadCards = (files: File[]) => files.length && void run("cards", async () => { const result = await uploadCardCatalog(files); setCatalog(`${result.cardCount} cards / ${result.attackCount} attacks`); onCatalogReady(); });
  const officialReady = Boolean(engine && player && opponent && !busy && liveStatus !== "connecting");

  return <section className="runtime-panel" aria-label="Official engine and Kaggle bundle loader">
    <div className="runtime-head"><div><span className="section-kicker">LOCAL OFFICIAL RUNTIME</span><h2>Engine / Kaggle Bundle</h2></div><span className={`runtime-state ${liveStatus}`}>LIVE {liveStatus.toUpperCase()}</span></div>
    {error && <div className="inline-error" role="alert">{error}</div>}
    <div className="artifact-grid">
      <article><strong>1. 公式エンジン</strong><p>{engine ? engine.filename : "ptcg_engine ZIP または libcg.so"}</p><small>{engine ? `${engine.sourceKind} · ${shortSha(engine.sha256)}` : "アップロード後、WSL2でローカルビルド"}</small><button type="button" onClick={() => engineRef.current?.click()} disabled={Boolean(busy)}>{busy === "engine" ? "Building…" : "Upload Engine"}</button></article>
      <article><strong>2. 自分のKaggle Bundle</strong><p>{player?.filename || ".tar.gz / .tgz"}</p><small>{player ? `60 cards · ${shortSha(player.sha256)}` : "main.py と deck.csv を検証"}</small><button type="button" onClick={() => playerRef.current?.click()} disabled={Boolean(busy)}>Upload Player</button></article>
      <article><strong>3. 相手Bundle</strong><p>{opponent?.filename || ".tar.gz / .tgz"}</p><small>{opponent ? `60 cards · ${shortSha(opponent.sha256)}` : "別Agentを同じ公式エンジンへ接続"}</small><button type="button" onClick={() => opponentRef.current?.click()} disabled={Boolean(busy)}>Upload Opponent</button></article>
      <article><strong>4. カードDB</strong><p>{catalog}</p><small>card_id_list / EN_Card_Data / attack mapping</small><button type="button" onClick={() => cardsRef.current?.click()} disabled={Boolean(busy)}>Upload 3 Files</button></article>
    </div>
    <div className="runtime-actions">
      <button type="button" onClick={onConnectEmulator} disabled={liveStatus === "connecting" || liveStatus === "connected"}>Connect Emulator</button>
      <button className="primary" type="button" disabled={!officialReady} onClick={() => engine && player && opponent && onConnectOfficial({ engine: "official", engine_id: engine.id, player_bundle_id: player.id, opponent_bundle_id: opponent.id })}>Start Official Match</button>
      <button type="button" onClick={onDisconnect} disabled={liveStatus === "disconnected"}>Disconnect</button>
    </div>
    <input ref={engineRef} className="file-input" type="file" accept=".zip,.so,application/zip" onChange={(event) => { loadEngine(event.target.files?.[0]); event.currentTarget.value = ""; }} />
    <input ref={playerRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip" onChange={(event) => { loadPlayer(event.target.files?.[0]); event.currentTarget.value = ""; }} />
    <input ref={opponentRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip" onChange={(event) => { loadOpponent(event.target.files?.[0]); event.currentTarget.value = ""; }} />
    <input ref={cardsRef} className="file-input" type="file" multiple accept=".csv,.json,text/csv,application/json" onChange={(event) => { loadCards(Array.from(event.target.files || [])); event.currentTarget.value = ""; }} />
  </section>;
}
