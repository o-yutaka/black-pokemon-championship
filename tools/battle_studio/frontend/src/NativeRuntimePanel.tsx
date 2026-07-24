import { useRef, useState } from "react";
import { getInitialBridgeUrl, persistBridgeUrl } from "./bridge-url";
import { appendFolder, chooseFolder, findEngineFile, folderFromInput, type PickedFolder } from "./folderPicker";
import type { LiveStatus } from "./live";
import "./native-runtime.css";

type EngineArtifact = { id: string; filename: string; sha256: string; sourceKind: string; compiler?: string | null };
type BundleArtifact = { id: string; filename: string; sha256: string; deckCount: number; uniqueCardIds: number; bundledEngineSha256?: string | null };
type CardCatalogInfo = { count: number; sources: string[]; folder: string };
type NativeStartRequest = { bridgeUrl: string; engine: "official-native"; engineId: string; playerBundleId: string; nativeOpponentBundleId: string };
type FolderRole = "cards" | "engine" | "player" | "opponent";

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
  const [busy, setBusy] = useState<string | null>(null);

  const bridgeUrl = (): string => persistBridgeUrl(getInitialBridgeUrl());

  const run = async (label: string, task: () => Promise<void>) => {
    setBusy(label);
    onError(null);
    try { await task(); }
    catch (error) { onError(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(null); }
  };

  const uploadEngine = (file?: File, displayName?: string) => file && void run("engine", async () => {
    const body = new FormData();
    body.append("file", file, displayName || file.name);
    const payload = await responseJson<{ engine: EngineArtifact }>(await fetch(new URL("/api/native/engine", bridgeUrl()), { method: "POST", body }));
    setEngine(payload.engine);
    setPlayer(null);
    setOpponent(null);
  });

  const uploadBundleFile = (role: "player" | "opponent", file?: File) => file && void run(role, async () => {
    const body = new FormData();
    body.append("file", file);
    const url = new URL("/api/native/bundles", bridgeUrl());
    if (engine) url.searchParams.set("engine_id", engine.id);
    const payload = await responseJson<{ bundle: BundleArtifact }>(await fetch(url, { method: "POST", body }));
    if (role === "player") setPlayer(payload.bundle); else setOpponent(payload.bundle);
  });

  const uploadFolder = (role: FolderRole, folder: PickedFolder) => {
    if (!folder.files.length) return;
    if (role === "engine") {
      const selected = findEngineFile(folder);
      uploadEngine(selected.file, selected.path);
      return;
    }
    void run(role, async () => {
      const body = new FormData();
      appendFolder(body, folder);
      if (role === "cards") {
        const payload = await responseJson<CardCatalogInfo>(await fetch(new URL("/api/cards/folder", bridgeUrl()), { method: "POST", body }));
        setCards(payload);
        return;
      }
      if (engine) body.append("engine_id", engine.id);
      const payload = await responseJson<{ bundle: BundleArtifact }>(await fetch(new URL("/api/native/bundle-folder", bridgeUrl()), { method: "POST", body }));
      if (role === "player") setPlayer(payload.bundle); else setOpponent(payload.bundle);
    });
  };

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
    <section className="native-runtime" aria-label="ローカル公式エンジンRuntime">
      <div className="native-runtime-head">
        <div><span className="eyebrow">かんたんフォルダー準備</span><h2>圧縮せず、フォルダーを選ぶだけ</h2><p>中身を自動判定する。カードDB、Engine、自分Agent、相手Agentの順に選べば対戦できる。</p></div>
        <span className={`native-state ${ready ? "ready" : "setup"}`}>{ready ? "開始可能" : busy ? "読み込み中" : "準備中"}</span>
      </div>
      <div className="native-grid folder-grid">
        <article className={cards ? "folder-ready" : ""}><strong>0. ポケカ画像・カードDB</strong><p>{cards ? `${cards.count}枚 · ${cards.sources.join(" + ")}` : "EN_Card_Data.csv と card_id_list.csv"}</p><small>{cards ? "実カード画像とカード名を使用" : "2ファイルが入ったフォルダーを選択"}</small><button className="folder-primary" type="button" onClick={() => void choose("cards")} disabled={Boolean(busy)}>{busy === "cards" ? "読込中…" : "フォルダーを選ぶ"}</button></article>
        <article className={engine ? "folder-ready" : ""}><strong>1. 公式エンジン</strong><p>{engine?.filename || "libcg.so または公式Engine ZIP"}</p><small>{engine ? `${engine.sourceKind} · ${shortSha(engine.sha256)}` : "フォルダー内から自動検出"}</small><button className="folder-primary" type="button" onClick={() => void choose("engine")} disabled={Boolean(busy)}>{busy === "engine" ? "ビルド中…" : "フォルダーを選ぶ"}</button><button className="minor-picker" type="button" onClick={() => engineFileRef.current?.click()} disabled={Boolean(busy)}>ファイルだけ選ぶ</button></article>
        <article className={player ? "folder-ready" : ""}><strong>2. 自分のAgent</strong><p>{player?.filename || "main.py + deck.csv のフォルダー"}</p><small>{player ? `${player.deckCount}枚 · ${shortSha(player.sha256)}` : "必要ファイルを自動検出・圧縮不要"}</small><button className="folder-primary" type="button" onClick={() => void choose("player")} disabled={!engine || Boolean(busy)}>{busy === "player" ? "検証中…" : "フォルダーを選ぶ"}</button><button className="minor-picker" type="button" onClick={() => playerFileRef.current?.click()} disabled={!engine || Boolean(busy)}>tar.gzを選ぶ</button></article>
        <article className={opponent ? "folder-ready" : ""}><strong>3. 相手のAgent</strong><p>{opponent?.filename || "main.py + deck.csv のフォルダー"}</p><small>{opponent ? `${opponent.deckCount}枚 · ${shortSha(opponent.sha256)}` : "別Agentのフォルダーをそのまま選択"}</small><button className="folder-primary" type="button" onClick={() => void choose("opponent")} disabled={!engine || Boolean(busy)}>{busy === "opponent" ? "検証中…" : "フォルダーを選ぶ"}</button><button className="minor-picker" type="button" onClick={() => opponentFileRef.current?.click()} disabled={!engine || Boolean(busy)}>tar.gzを選ぶ</button></article>
      </div>
      <button className="native-start primary" type="button" disabled={!ready} onClick={() => engine && player && opponent && onStart({ bridgeUrl: bridgeUrl(), engine: "official-native", engineId: engine.id, playerBundleId: player.id, nativeOpponentBundleId: opponent.id })}>公式対戦を開始</button>
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
