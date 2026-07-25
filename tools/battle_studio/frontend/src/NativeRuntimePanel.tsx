import { useEffect, useMemo, useRef, useState } from "react";
import { getInitialBridgeUrl, persistBridgeUrl } from "./bridge-url";
import { inspectAgentAnalysis, type AgentAnalysisContext } from "./deck-analysis";
import { APPLY_PLAYER_DECK_EVENT, dispatchBundleDeck, dispatchPlayerBundleSelected, dispatchPlayerBundleUpdated, type ApplyPlayerDeckDetail, type BundleSummary } from "./deck-easy";
import { appendFolder, chooseFolder, findEngineFile, folderFromInput, replaceAgentDeck, type PickedFolder } from "./folderPicker";
import { buildOpponentPresets, loadStoredOpponent, preferredOpponent, saveStoredOpponent, type PresetBundle } from "./opponent-presets";
import type { LiveStatus } from "./live";
import "./native-runtime.css";

type EngineArtifact = { id: string; filename: string; sha256: string; sourceKind: string; compiler?: string | null };
type BundleArtifact = BundleSummary;
type CardCatalogInfo = { count: number; sources: string[]; folder: string };
type NativeStartRequest = { bridgeUrl: string; engine: "official-native"; engineId: string; playerBundleId: string; nativeOpponentBundleId: string };
type FolderRole = "cards" | "engine" | "player" | "opponent";
type ArtifactPayload = { engines: EngineArtifact[]; bundles: BundleArtifact[] };

type Props = {
  liveStatus: LiveStatus;
  onStart(request: NativeStartRequest): void;
  onError(message: string | null): void;
};

async function responseJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({})) as T & { detail?: string };
  if (!response.ok) throw new Error(payload.detail || `通信エラー（HTTP ${response.status}）`);
  return payload;
}

function shortSha(value?: string | null): string {
  return value ? `${value.slice(0, 12)}…` : "—";
}

const directoryAttributes = { webkitdirectory: "", directory: "" } as Record<string, string>;

export function NativeRuntimePanel({ liveStatus, onStart, onError }: Props) {
  const engineFileRef = useRef<HTMLInputElement>(null);
  const playerFileRef = useRef<HTMLInputElement>(null);
  const opponentFileRef = useRef<HTMLInputElement>(null);
  const cardFolderRef = useRef<HTMLInputElement>(null);
  const engineFolderRef = useRef<HTMLInputElement>(null);
  const playerFolderRef = useRef<HTMLInputElement>(null);
  const opponentFolderRef = useRef<HTMLInputElement>(null);
  const [cards, setCards] = useState<CardCatalogInfo | null>(null);
  const [engine, setEngine] = useState<EngineArtifact | null>(null);
  const [player, setPlayer] = useState<BundleArtifact | null>(null);
  const [opponent, setOpponent] = useState<BundleArtifact | null>(null);
  const [registeredBundles, setRegisteredBundles] = useState<BundleArtifact[]>([]);
  const [storedOpponent] = useState(() => loadStoredOpponent());
  const [playerSourceFolder, setPlayerSourceFolder] = useState<PickedFolder | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const bridgeUrl = (): string => persistBridgeUrl(getInitialBridgeUrl());

  const run = async (label: string, task: () => Promise<void>) => {
    setBusy(label);
    onError(null);
    try { await task(); }
    catch (error) { onError(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(null); }
  };

  const refreshArtifacts = async () => {
    const payload = await responseJson<ArtifactPayload>(await fetch(new URL("/api/native/artifacts", bridgeUrl()), { cache: "no-store" }));
    setRegisteredBundles(payload.bundles);
  };

  const publishPlayer = (bundle: BundleArtifact, deck: number[], sourceFolder: PickedFolder | null, analysis: AgentAnalysisContext | null, updated = false) => {
    setPlayer(bundle);
    setPlayerSourceFolder(sourceFolder);
    dispatchBundleDeck(deck);
    const detail = { bundle, deck, canApplyDirectly: Boolean(sourceFolder), analysis };
    if (updated) dispatchPlayerBundleUpdated(detail); else dispatchPlayerBundleSelected(detail);
  };

  const emptyAnalysis = (bundle: BundleArtifact): AgentAnalysisContext => ({
    report: null,
    reportSource: null,
    policySha: null,
    freezeSha: null,
    engineSha: engine?.sha256 ?? null,
    bundleSha: bundle.sha256,
    bundledEngineSha: bundle.bundledEngineSha256 ?? null,
  });

  const selectOpponent = (bundle: BundleArtifact) => {
    setOpponent(bundle);
    saveStoredOpponent(bundle as PresetBundle);
  };

  const uploadEngine = (file?: File, displayName?: string) => file && void run("engine", async () => {
    const body = new FormData();
    body.append("file", file, displayName || file.name);
    const payload = await responseJson<{ engine: EngineArtifact }>(await fetch(new URL("/api/native/engine", bridgeUrl()), { method: "POST", body }));
    setEngine(payload.engine);
    setPlayer(null);
    setOpponent(null);
    setPlayerSourceFolder(null);
    await refreshArtifacts();
  });

  const uploadBundleFile = (role: "player" | "opponent", file?: File) => file && void run(role, async () => {
    const body = new FormData();
    body.append("file", file);
    const url = new URL("/api/native/bundles", bridgeUrl());
    if (engine) url.searchParams.set("engine_id", engine.id);
    const payload = await responseJson<{ bundle: BundleArtifact; deck: number[] }>(await fetch(url, { method: "POST", body }));
    if (role === "player") publishPlayer(payload.bundle, payload.deck, null, emptyAnalysis(payload.bundle)); else selectOpponent(payload.bundle);
    await refreshArtifacts();
  });

  const uploadAgentFolder = async (role: "player" | "opponent", folder: PickedFolder, updated = false) => {
    const body = new FormData();
    appendFolder(body, folder);
    if (engine) body.append("engine_id", engine.id);
    const payload = await responseJson<{ bundle: BundleArtifact; deck: number[] }>(await fetch(new URL("/api/native/bundle-folder", bridgeUrl()), { method: "POST", body }));
    if (role === "player") {
      const analysis = await inspectAgentAnalysis(folder, { engineSha: engine?.sha256 ?? null, bundleSha: payload.bundle.sha256, bundledEngineSha: payload.bundle.bundledEngineSha256 });
      publishPlayer(payload.bundle, payload.deck, folder, analysis, updated);
    } else selectOpponent(payload.bundle);
    await refreshArtifacts();
  };

  const uploadFolder = (role: FolderRole, folder: PickedFolder) => {
    if (!folder.files.length) return;
    if (role === "engine") {
      const selected = findEngineFile(folder);
      uploadEngine(selected.file, selected.path);
      return;
    }
    void run(role, async () => {
      if (role === "cards") {
        const body = new FormData();
        appendFolder(body, folder);
        const payload = await responseJson<CardCatalogInfo>(await fetch(new URL("/api/cards/folder", bridgeUrl()), { method: "POST", body }));
        setCards(payload);
        window.dispatchEvent(new Event("black:card-catalog-updated"));
        return;
      }
      await uploadAgentFolder(role, folder);
    });
  };

  useEffect(() => {
    const applyDeck = (event: Event) => {
      const detail = (event as CustomEvent<ApplyPlayerDeckDetail>).detail;
      if (!Array.isArray(detail?.deck)) return;
      if (!engine) { onError("先に公式対戦エンジンを選んでください"); return; }
      if (!playerSourceFolder) { onError("直接反映するには、自分の対戦AIを『フォルダーを選ぶ』から読み込んでください"); return; }
      void run("player", async () => {
        const modified = replaceAgentDeck(playerSourceFolder, detail.deck);
        await uploadAgentFolder("player", modified, true);
      });
    };
    window.addEventListener(APPLY_PLAYER_DECK_EVENT, applyDeck);
    return () => window.removeEventListener(APPLY_PLAYER_DECK_EVENT, applyDeck);
  }, [engine, playerSourceFolder]);

  const presets = useMemo(() => buildOpponentPresets({ engine, player, bundles: registeredBundles, stored: storedOpponent }), [engine, player, registeredBundles, storedOpponent]);

  useEffect(() => {
    if (opponent || !engine || !player) return;
    const selected = preferredOpponent(presets);
    if (selected) selectOpponent(selected as BundleArtifact);
  }, [engine, opponent, player, presets]);

  const folderFallbackRef = (role: FolderRole) => ({ cards: cardFolderRef, engine: engineFolderRef, player: playerFolderRef, opponent: opponentFolderRef }[role]);
  const choose = async (role: FolderRole) => {
    try {
      const selected = await chooseFolder();
      if (selected === null) folderFallbackRef(role).current?.click();
      else uploadFolder(role, selected);
    } catch (error) {
      onError(error instanceof Error ? error.message : String(error));
    }
  };
  const inputFolder = (role: FolderRole, files: FileList | null) => {
    const folder = folderFromInput(files);
    if (folder) uploadFolder(role, folder);
  };

  const ready = Boolean(engine && player && opponent && !busy && liveStatus !== "connecting" && liveStatus !== "connected");

  return (
    <section className="native-runtime" aria-label="ローカル公式対戦の準備">
      <div className="native-runtime-head">
        <div><span className="eyebrow">かんたん対戦準備</span><h2>相手はプリセットから1タップ</h2><p>カード情報・公式エンジン・自分の対戦AIを選べば、相手は前回・ミラー・登録済み候補からすぐ選べる。</p></div>
        <span className={`native-state ${ready ? "ready" : "setup"}`}>{ready ? "対戦開始できます" : busy ? "読み込み中" : "準備中"}</span>
      </div>
      <div className="native-grid folder-grid">
        <article className={cards ? "folder-ready" : ""}><strong>0. カード情報と画像</strong><p>{cards ? `${cards.count}枚 · ${cards.sources.join(" + ")}` : "カードDBの2つのCSV"}</p><small>{cards ? "実カード画像とカード名を使用中" : "CSVが入ったフォルダーを選ぶ"}</small><button className="folder-primary" type="button" onClick={() => void choose("cards")} disabled={Boolean(busy)}>{busy === "cards" ? "読み込み中…" : "フォルダーを選ぶ"}</button></article>
        <article className={engine ? "folder-ready" : ""}><strong>1. 公式対戦エンジン</strong><p>{engine?.filename || "libcg.so または公式ZIP"}</p><small>{engine ? `${engine.sourceKind} · ${shortSha(engine.sha256)}` : "中から自動で見つけます"}</small><button className="folder-primary" type="button" onClick={() => void choose("engine")} disabled={Boolean(busy)}>{busy === "engine" ? "準備中…" : "フォルダーを選ぶ"}</button><button className="minor-picker" type="button" onClick={() => engineFileRef.current?.click()} disabled={Boolean(busy)}>ファイルを直接選ぶ</button></article>
        <article className={player ? "folder-ready" : ""}><strong>2. 自分の対戦AI</strong><p>{player?.filename || "main.pyとdeck.csvのフォルダー"}</p><small>{player ? `${player.deckCount}枚 · ${playerSourceFolder ? "分析・デッキ変更可能" : "圧縮ファイル読込"}` : "選ぶとデッキと分析情報を自動読込"}</small><button className="folder-primary" type="button" onClick={() => void choose("player")} disabled={!engine || Boolean(busy)}>{busy === "player" ? "確認中…" : "フォルダーを選ぶ"}</button><button className="minor-picker" type="button" onClick={() => playerFileRef.current?.click()} disabled={!engine || Boolean(busy)}>圧縮ファイルを選ぶ</button></article>
        <article className={opponent ? "folder-ready opponent-setup-card" : "opponent-setup-card"}><strong>3. 相手の対戦AI</strong><p>{opponent?.filename || "プリセットを選択"}</p><small>{opponent ? `${opponent.deckCount}枚 · ${shortSha(opponent.sha256)}` : engine && player ? "使える候補を自動表示中" : "先にEngineと自分Agentを選ぶ"}</small>
          <div className="opponent-presets" aria-label="相手プリセット">
            {presets.map((preset) => <button key={preset.key} type="button" className={`opponent-preset ${opponent?.sha256 === preset.bundle?.sha256 ? "selected" : ""}`} disabled={!preset.available || Boolean(busy)} onClick={() => preset.bundle && selectOpponent(preset.bundle as BundleArtifact)} title={preset.reason ?? preset.description}><strong>{preset.label}</strong><span>{preset.available ? preset.description : preset.reason}</span></button>)}
            {!presets.length && <div className="opponent-preset-empty">自分Agentを選ぶと「自分ミラー」が使えます。別候補は一度登録するとここへ並びます。</div>}
          </div>
          <button className="folder-primary opponent-custom" type="button" onClick={() => void choose("opponent")} disabled={!engine || Boolean(busy)}>{busy === "opponent" ? "確認中…" : "別の相手フォルダーを選ぶ"}</button><button className="minor-picker" type="button" onClick={() => opponentFileRef.current?.click()} disabled={!engine || Boolean(busy)}>相手の圧縮ファイルを選ぶ</button></article>
      </div>
      <button className="native-start primary" type="button" disabled={!ready} onClick={() => engine && player && opponent && onStart({ bridgeUrl: bridgeUrl(), engine: "official-native", engineId: engine.id, playerBundleId: player.id, nativeOpponentBundleId: opponent.id })}>この2つの対戦AIで公式対戦を始める</button>
      <input ref={engineFileRef} className="file-input" type="file" accept=".zip,.so,application/zip,application/octet-stream" onChange={(event) => { uploadEngine(event.target.files?.[0]); event.currentTarget.value = ""; }} />
      <input ref={playerFileRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip" onChange={(event) => { uploadBundleFile("player", event.target.files?.[0]); event.currentTarget.value = ""; }} />
      <input ref={opponentFileRef} className="file-input" type="file" accept=".tgz,.gz,.tar.gz,application/gzip" onChange={(event) => { uploadBundleFile("opponent", event.target.files?.[0]); event.currentTarget.value = ""; }} />
      <input ref={cardFolderRef} className="file-input" type="file" multiple {...directoryAttributes} onChange={(event) => { inputFolder("cards", event.target.files); event.currentTarget.value = ""; }} />
      <input ref={engineFolderRef} className="file-input" type="file" multiple {...directoryAttributes} onChange={(event) => { inputFolder("engine", event.target.files); event.currentTarget.value = ""; }} />
      <input ref={playerFolderRef} className="file-input" type="file" multiple {...directoryAttributes} onChange={(event) => { inputFolder("player", event.target.files); event.currentTarget.value = ""; }} />
      <input ref={opponentFolderRef} className="file-input" type="file" multiple {...directoryAttributes} onChange={(event) => { inputFolder("opponent", event.target.files); event.currentTarget.value = ""; }} />
    </section>
  );
}
