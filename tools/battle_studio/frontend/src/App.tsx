import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { CardFace, selectedCardWithArt, type MotionMode } from "./BattleBoard";
import { useCardArtCatalog, type PublicCardCatalogEntry } from "./cardArt";
import { demoReplay } from "./demo";
import { DecisionIDE } from "./DecisionIDE";
import { EngineConsole, type EngineStartRequest } from "./EngineConsole";
import { connectLive, mergeLiveSnapshotFrames, type LiveConnection, type LiveSnapshot, type LiveStatus, type ViewMode } from "./live";
import { motionModeJa, phaseJa, zoneJa } from "./locale";
import { NativeRuntimePanel } from "./NativeRuntimePanel";
import { OfficialScoreDashboardDialog } from "./OfficialScoreDashboard";
import { analyzeReplayFailure, publishReplayFailureReport, REPLAY_EVIDENCE_FRAME_EVENT } from "./replay-failure";
import { readReplayFile } from "./replay";
import { RuntimeTruthBadge } from "./RuntimeTruthBadge";
import { liveSurfaceLabel } from "./runtime-health";
import type { BattleFrame, BattleReplay, CardInstance } from "./types";
import "./styles.css";
import "./pocket-ui.css";
import "./simulator-ui.css";

const SPEEDS = [0.25, 0.5, 1, 2, 4] as const;
const MOTION_MODES: MotionMode[] = ["full", "balanced", "lite"];

function defaultMotionMode(): MotionMode {
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return "lite";
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 8;
  return memory <= 4 || window.innerWidth <= 720 ? "balanced" : "full";
}

function frameCardIds(frame: BattleFrame): number[] {
  const ids = new Set<number>();
  const add = (card: CardInstance | null | undefined) => { if (card && card.cardId > 0) ids.add(card.cardId); };
  add(frame.stadium);
  for (const player of frame.players) {
    add(player.active);
    player.bench.forEach(add);
    player.hand.forEach(add);
    player.deck.forEach(add);
    player.prize.forEach(add);
    player.discard.forEach(add);
  }
  return [...ids];
}

export default function App() {
  const [replay, setReplay] = useState<BattleReplay>(demoReplay);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const [motionMode, setMotionMode] = useState<MotionMode>(() => (localStorage.getItem("black-motion-mode") as MotionMode | null) ?? defaultMotionMode());
  const [selectedCard, setSelectedCard] = useState<CardInstance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<LiveStatus>("disconnected");
  const [liveEngine, setLiveEngine] = useState<string | null>(null);
  const [legalSelections, setLegalSelections] = useState<number[][]>([]);
  const [liveCanAdvance, setLiveCanAdvance] = useState(false);
  const [simulatorAvailable, setSimulatorAvailable] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("player");
  const [publicCards, setPublicCards] = useState<PublicCardCatalogEntry[]>([]);
  const [showSetup, setShowSetup] = useState(false);
  const [showOfficialScores, setShowOfficialScores] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const liveRef = useRef<LiveConnection | null>(null);
  const frame = replay.frames[Math.min(frameIndex, replay.frames.length - 1)];
  const previousFrame = frameIndex > 0 ? replay.frames[frameIndex - 1] : null;
  const visibleCardIds = useMemo(() => frameCardIds(frame), [frame]);
  const catalog = useCardArtCatalog(visibleCardIds, publicCards);
  const progress = replay.frames.length <= 1 ? 0 : (frameIndex / (replay.frames.length - 1)) * 100;
  const isLive = liveStatus === "connected";
  const actionReady = liveCanAdvance || legalSelections.length > 0;
  const surfaceLabel = liveSurfaceLabel(liveStatus, liveEngine, replay.source);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setFrameIndex((current) => {
      if (current >= replay.frames.length - 1) { setPlaying(false); return current; }
      return current + 1;
    }), Math.max(80, 900 / speed));
    return () => window.clearInterval(timer);
  }, [playing, replay.frames.length, speed]);
  useEffect(() => setSelectedCard(null), [frameIndex]);
  useEffect(() => () => liveRef.current?.close(), []);
  useEffect(() => localStorage.setItem("black-motion-mode", motionMode), [motionMode]);
  useEffect(() => publishReplayFailureReport(analyzeReplayFailure(replay, 0)), [replay]);

  const selectFrame = (index: number) => {
    setPlaying(false);
    setFrameIndex(Math.max(0, Math.min(replay.frames.length - 1, index)));
  };

  useEffect(() => {
    const openEvidence = (event: Event) => {
      const detail = (event as CustomEvent<{ replayId?: string; frameId?: number }>).detail;
      if (!detail || detail.replayId !== replay.replayId || !Number.isInteger(detail.frameId)) return;
      const index = replay.frames.findIndex((item) => item.frameId === detail.frameId);
      if (index >= 0) selectFrame(index);
    };
    window.addEventListener(REPLAY_EVIDENCE_FRAME_EVENT, openEvidence);
    return () => window.removeEventListener(REPLAY_EVIDENCE_FRAME_EVENT, openEvidence);
  }, [replay]);

  const applyLiveSnapshot = (snapshot: LiveSnapshot) => {
    setLiveEngine(snapshot.engine);
    setLegalSelections(snapshot.legalSelections);
    setLiveCanAdvance(snapshot.controls.canAdvance);
    setSimulatorAvailable(snapshot.controls.simulatorAvailable);
    setViewMode(snapshot.controls.viewMode);
    setPublicCards(snapshot.cardCatalog);
    if (snapshot.hiddenInformationPolicy === "player_view") setSelectedCard(null);
    setReplay((current) => {
      const frames = mergeLiveSnapshotFrames(current, snapshot);
      window.setTimeout(() => setFrameIndex(frames.length - 1), 0);
      return {
        schemaVersion: "1.0",
        replayId: snapshot.sessionId,
        createdAt: new Date().toISOString(),
        source: snapshot.publicProtocol ? "cabt" : "unknown",
        hiddenInformationPolicy: snapshot.hiddenInformationPolicy,
        frames,
      };
    });
  };

  const disconnectLive = () => {
    liveRef.current?.close();
    liveRef.current = null;
    setLiveStatus("disconnected");
    setLiveEngine(null);
    setLegalSelections([]);
    setLiveCanAdvance(false);
    setSimulatorAvailable(false);
    setViewMode("player");
    setPublicCards([]);
    setSelectedCard(null);
  };

  const startEngine = async (request: EngineStartRequest) => {
    setError(null);
    setPlaying(false);
    disconnectLive();
    try {
      liveRef.current = await connectLive(
        request.bridgeUrl,
        { engine: request.engine, bundleId: request.bundleId, opponentBundleId: request.opponentBundleId, engineId: request.engineId, playerBundleId: request.playerBundleId, nativeOpponentBundleId: request.nativeOpponentBundleId },
        applyLiveSnapshot,
        setLiveStatus,
        setError,
      );
      setLiveEngine(liveRef.current.engine);
      setShowSetup(false);
    } catch (caught) {
      setLiveStatus("error");
      setError(caught instanceof Error ? caught.message : "対戦画面へ接続できませんでした");
      setShowSetup(true);
    }
  };

  const loadFile = async (file: File | undefined) => {
    if (!file) return;
    disconnectLive();
    setError(null);
    setPlaying(false);
    try {
      const next = await readReplayFile(file);
      setReplay(next);
      setFrameIndex(0);
      setShowSetup(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "対戦記録を読み込めませんでした");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const stepLive = () => liveRef.current?.step(legalSelections[0]);
  const toggleSimulator = () => liveRef.current?.setViewMode(viewMode === "simulator" ? "player" : "simulator");
  const selectedWithArt = selectedCard ? selectedCardWithArt(selectedCard, catalog) : null;

  return (
    <main className={`app-shell pocket-shell game-shell ${viewMode === "simulator" ? "simulator-active" : ""}`}>
      <input ref={fileRef} className="file-input" type="file" accept="application/json,.json,.jsonl,.ndjson" onChange={(event) => void loadFile(event.target.files?.[0])} />

      <header className="game-topbar">
        <div className="game-brand"><span className="brand-ball" /><div><strong>BLACK BATTLE</strong><small>{surfaceLabel}</small></div></div>
        <div className="game-top-actions"><RuntimeTruthBadge /><button className="official-score-launch" type="button" onClick={() => setShowOfficialScores(true)}>公式row記録 <b>844.4</b></button><button type="button" onClick={() => fileRef.current?.click()} aria-label="対戦記録を開く">記録</button><button className="primary" type="button" onClick={() => setShowSetup(true)}>対戦準備</button></div>
      </header>

      <section className="game-hud" aria-label="対戦状況">
        <div><span className={`live-dot ${liveStatus}`} /><strong>{frame.players[1].name}</strong><small>サイド {frame.players[1].prizeCount}</small></div>
        <div className="turn-orb"><span>TURN</span><strong>{frame.turn}</strong><small>{phaseJa(frame.phase)}</small></div>
        <div><strong>{frame.players[0].name}</strong><small>サイド {frame.players[0].prizeCount}</small></div>
      </section>

      {viewMode === "simulator" && <div className="simulator-banner" role="status"><strong>シミュレーターモード ON</strong><span>両者の非公開カードを表示中。OFFへ戻すと即座に隠れます。</span></div>}
      {error && <div className="error-banner friendly-error" role="alert"><strong>開けませんでした</strong><span>{error}</span><button type="button" onClick={() => setError(null)}>閉じる</button></div>}

      {showOfficialScores && <OfficialScoreDashboardDialog onClose={() => setShowOfficialScores(false)} />}
      {showSetup && <div className="sheet-backdrop" role="presentation" onMouseDown={() => setShowSetup(false)}><section className="setup-sheet game-setup-sheet" role="dialog" aria-modal="true" aria-label="対戦準備" onMouseDown={(event) => event.stopPropagation()}><header><div><span>対戦準備</span><h2>3つ選んで開始</h2><p>公式エンジン、自分のAI、相手。</p></div><button type="button" onClick={() => setShowSetup(false)}>閉じる</button></header><NativeRuntimePanel liveStatus={liveStatus} onStart={(request) => void startEngine(request)} onError={setError} /><details className="advanced-setup"><summary>外部Runner・エミュレーター</summary><EngineConsole liveStatus={liveStatus} liveEngine={liveEngine} legalSelectionCount={legalSelections.length} canAdvance={liveCanAdvance} onStart={(request) => void startEngine(request)} onStep={stepLive} onDisconnect={disconnectLive} onError={setError} /></details></section></div>}

      <DecisionIDE replay={replay} frame={frame} previousFrame={previousFrame} frameIndex={frameIndex} onSelectFrame={selectFrame} onSelectCard={setSelectedCard} catalog={catalog} motionMode={motionMode} />

      <section className={`game-action-dock ${isLive ? "live" : "replay"}`} aria-label="対戦操作">
        {isLive ? <><button className="battle-action primary" type="button" onClick={stepLive} disabled={!actionReady}>次へ</button>{simulatorAvailable && <button className={`simulator-toggle ${viewMode === "simulator" ? "on" : "off"}`} type="button" onClick={toggleSimulator}>全カード {viewMode === "simulator" ? "ON" : "OFF"}</button>}<button className="dock-minor" type="button" onClick={disconnectLive}>終了</button></> : <><button type="button" onClick={() => selectFrame(frameIndex - 1)} disabled={frameIndex === 0} aria-label="1つ戻る">◀</button><button className="battle-action primary" type="button" onClick={() => setPlaying((value) => !value)}>{playing ? "停止" : "再生"}</button><button type="button" onClick={() => selectFrame(frameIndex + 1)} disabled={frameIndex === replay.frames.length - 1} aria-label="1つ進む">▶</button></>}
        <details className="dock-more"><summary aria-label="その他の操作">•••</summary><div><button type="button" onClick={() => selectFrame(0)} disabled={frameIndex === 0}>最初</button><label>場面 {frameIndex + 1}/{replay.frames.length}<input type="range" min="0" max={Math.max(0, replay.frames.length - 1)} value={Math.min(frameIndex, replay.frames.length - 1)} onChange={(event) => selectFrame(Number(event.target.value))} style={{ "--progress": `${progress}%` } as CSSProperties} /></label><label>速度<select value={speed} onChange={(event) => setSpeed(Number(event.target.value) as (typeof SPEEDS)[number])}>{SPEEDS.map((value) => <option key={value} value={value}>{value}倍</option>)}</select></label><label>演出<select value={motionMode} onChange={(event) => setMotionMode(event.target.value as MotionMode)}>{MOTION_MODES.map((mode) => <option key={mode} value={mode}>{motionModeJa(mode)}</option>)}</select></label><button type="button" onClick={() => selectFrame(replay.frames.length - 1)} disabled={frameIndex === replay.frames.length - 1}>最後</button></div></details>
      </section>

      {selectedWithArt && <div className="modal-backdrop" role="presentation" onMouseDown={() => setSelectedCard(null)}><section className="card-modal" role="dialog" aria-modal="true" aria-label={selectedWithArt.name} onMouseDown={(event) => event.stopPropagation()}><button className="close-button" type="button" onClick={() => setSelectedCard(null)}>閉じる</button><CardFace card={selectedWithArt} catalog={catalog} /><dl><div><dt>場所</dt><dd>{zoneJa(selectedWithArt.zone)}{selectedWithArt.slot === null ? "" : ` / 枠${selectedWithArt.slot + 1}`}</dd></div><div><dt>進化</dt><dd>{selectedWithArt.evolution.length ? `${selectedWithArt.evolution.length}段階` : "なし"}</dd></div><div><dt>どうぐ</dt><dd>{selectedWithArt.tools.length ? selectedWithArt.tools.join(", ") : "なし"}</dd></div></dl></section></div>}
    </main>
  );
}
