import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { CardFace, selectedCardWithArt, type MotionMode } from "./BattleBoard";
import { useCardArtCatalog } from "./cardArt";
import { demoReplay } from "./demo";
import { DecisionIDE } from "./DecisionIDE";
import { EngineConsole, type EngineStartRequest } from "./EngineConsole";
import { connectLive, type LiveConnection, type LiveSnapshot, type LiveStatus } from "./live";
import { liveStatusJa, motionModeJa, phaseJa, zoneJa } from "./locale";
import { NativeRuntimePanel } from "./NativeRuntimePanel";
import { analyzeReplayFailure, publishReplayFailureReport, REPLAY_EVIDENCE_FRAME_EVENT } from "./replay-failure";
import { readReplayFile } from "./replay";
import { cardKey, type BattleFrame, type BattleReplay, type CardInstance } from "./types";
import "./styles.css";
import "./pocket-ui.css";

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
  const fileRef = useRef<HTMLInputElement>(null);
  const liveRef = useRef<LiveConnection | null>(null);
  const frame = replay.frames[Math.min(frameIndex, replay.frames.length - 1)];
  const previousFrame = frameIndex > 0 ? replay.frames[frameIndex - 1] : null;
  const visibleCardIds = useMemo(() => frameCardIds(frame), [frame]);
  const catalog = useCardArtCatalog(visibleCardIds);
  const progress = replay.frames.length <= 1 ? 0 : (frameIndex / (replay.frames.length - 1)) * 100;

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

  const frameLabel = useMemo(() => `ターン ${frame.turn} · ${phaseJa(frame.phase)} · 行動 ${frame.actionCount}`, [frame]);
  const selectFrame = (index: number) => { setPlaying(false); setFrameIndex(Math.max(0, Math.min(replay.frames.length - 1, index))); };
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
    setLiveEngine(snapshot.engine); setLegalSelections(snapshot.legalSelections);
    setReplay((current) => {
      const frames = current.replayId === snapshot.sessionId ? [...current.frames.filter((item) => item.frameId !== snapshot.frame.frameId), snapshot.frame].sort((a, b) => a.frameId - b.frameId) : [snapshot.frame];
      window.setTimeout(() => setFrameIndex(frames.length - 1), 0);
      return { schemaVersion: "1.0", replayId: snapshot.sessionId, createdAt: new Date().toISOString(), source: "unknown", hiddenInformationPolicy: "spectator", frames };
    });
  };
  const disconnectLive = () => { liveRef.current?.close(); liveRef.current = null; setLiveStatus("disconnected"); setLiveEngine(null); setLegalSelections([]); };
  const startEngine = async (request: EngineStartRequest) => {
    setError(null); setPlaying(false); disconnectLive();
    try {
      liveRef.current = await connectLive(request.bridgeUrl, { engine: request.engine, bundleId: request.bundleId, opponentBundleId: request.opponentBundleId, engineId: request.engineId, playerBundleId: request.playerBundleId, nativeOpponentBundleId: request.nativeOpponentBundleId }, applyLiveSnapshot, setLiveStatus, setError);
      setLiveEngine(liveRef.current.engine);
    } catch (caught) { setLiveStatus("error"); setError(caught instanceof Error ? caught.message : "対戦画面へ接続できませんでした"); }
  };
  const loadFile = async (file: File | undefined) => {
    if (!file) return; disconnectLive(); setError(null); setPlaying(false);
    try { const next = await readReplayFile(file); setReplay(next); setFrameIndex(0); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "対戦記録を読み込めませんでした"); }
  };
  const selectedWithArt = selectedCard ? selectedCardWithArt(selectedCard, catalog) : null;

  return <main className="app-shell">
    <header className="topbar"><div><h1>BLACK Battle Studio</h1><p>判断解析 · 対戦記録 {replay.replayId} · {frameLabel} · 接続 {liveStatusJa(liveStatus)}</p></div><div className="top-actions"><label className="motion-picker">演出<select value={motionMode} onChange={(event) => setMotionMode(event.target.value as MotionMode)}>{MOTION_MODES.map((mode) => <option key={mode} value={mode}>{motionModeJa(mode)}</option>)}</select></label><input ref={fileRef} className="file-input" type="file" accept="application/json,.json" onChange={(event) => void loadFile(event.target.files?.[0])} /><button type="button" onClick={() => fileRef.current?.click()}>対戦記録を開く</button><button type="button" onClick={() => { disconnectLive(); setReplay(demoReplay); setFrameIndex(0); setPlaying(false); setError(null); }}>見本を表示</button></div></header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <EngineConsole liveStatus={liveStatus} liveEngine={liveEngine} legalSelectionCount={legalSelections.length} onStart={(request) => void startEngine(request)} onStep={() => liveRef.current?.step(legalSelections[0] ?? [0])} onDisconnect={disconnectLive} onError={setError} />
    <NativeRuntimePanel liveStatus={liveStatus} onStart={(request) => void startEngine(request)} onError={setError} />
    <DecisionIDE replay={replay} frame={frame} previousFrame={previousFrame} frameIndex={frameIndex} onSelectFrame={selectFrame} onSelectCard={setSelectedCard} catalog={catalog} motionMode={motionMode} />
    <section className="controls" aria-label="対戦記録の操作"><div className="control-buttons"><button type="button" onClick={() => selectFrame(0)} disabled={frameIndex === 0} aria-label="最初へ">⏮</button><button type="button" onClick={() => selectFrame(frameIndex - 1)} disabled={frameIndex === 0} aria-label="1つ戻る">◀</button><button className="primary" type="button" onClick={() => setPlaying((value) => !value)}>{playing ? "一時停止" : "再生"}</button><button type="button" onClick={() => selectFrame(frameIndex + 1)} disabled={frameIndex === replay.frames.length - 1} aria-label="1つ進む">▶</button><button type="button" onClick={() => selectFrame(replay.frames.length - 1)} disabled={frameIndex === replay.frames.length - 1} aria-label="最後へ">⏭</button></div><label className="timeline-label">場面 {Math.min(frameIndex + 1, replay.frames.length)}/{replay.frames.length}<input type="range" min="0" max={Math.max(0, replay.frames.length - 1)} value={Math.min(frameIndex, replay.frames.length - 1)} onChange={(event) => selectFrame(Number(event.target.value))} style={{ "--progress": `${progress}%` } as CSSProperties} /></label><label className="speed-label">再生速度<select value={speed} onChange={(event) => setSpeed(Number(event.target.value) as (typeof SPEEDS)[number])}>{SPEEDS.map((value) => <option key={value} value={value}>{value}倍</option>)}</select></label></section>
    {selectedWithArt && <div className="modal-backdrop" role="presentation" onMouseDown={() => setSelectedCard(null)}><section className="card-modal" role="dialog" aria-modal="true" aria-label={selectedWithArt.name} onMouseDown={(event) => event.stopPropagation()}><button className="close-button" type="button" onClick={() => setSelectedCard(null)}>閉じる</button><CardFace card={selectedWithArt} catalog={catalog} /><dl><div><dt>カード識別</dt><dd>{cardKey(selectedWithArt)}</dd></div><div><dt>現在の場所</dt><dd>{zoneJa(selectedWithArt.zone)}{selectedWithArt.slot === null ? "" : ` / 枠${selectedWithArt.slot + 1}`}</dd></div><div><dt>進化の履歴</dt><dd>{selectedWithArt.evolution.length ? selectedWithArt.evolution.join(" → ") : "記録なし"}</dd></div><div><dt>ついているどうぐ</dt><dd>{selectedWithArt.tools.length ? selectedWithArt.tools.join(", ") : "なし"}</dd></div></dl></section></div>}
  </main>;
}
