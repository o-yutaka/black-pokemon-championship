import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { CardFace } from "./BattleBoard";
import { demoReplay } from "./demo";
import { DecisionIDE } from "./DecisionIDE";
import { EngineConsole, type EngineStartRequest } from "./EngineConsole";
import { connectLive, type LiveConnection, type LiveSnapshot, type LiveStatus } from "./live";
import { liveStatusJa } from "./locale";
import { NativeRuntimePanel } from "./NativeRuntimePanel";
import { readReplayFile } from "./replay";
import { cardKey, type BattleReplay, type CardInstance } from "./types";
import "./styles.css";

const SPEEDS = [0.25, 0.5, 1, 2, 4] as const;

export default function App() {
  const [replay, setReplay] = useState<BattleReplay>(demoReplay);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const [selectedCard, setSelectedCard] = useState<CardInstance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<LiveStatus>("disconnected");
  const [liveEngine, setLiveEngine] = useState<string | null>(null);
  const [legalSelections, setLegalSelections] = useState<number[][]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const liveRef = useRef<LiveConnection | null>(null);
  const frame = replay.frames[Math.min(frameIndex, replay.frames.length - 1)];
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

  const frameLabel = useMemo(() => `ターン ${frame.turn} · ${frame.phase} · 行動 ${frame.actionCount}`, [frame]);
  const selectFrame = (index: number) => { setPlaying(false); setFrameIndex(Math.max(0, Math.min(replay.frames.length - 1, index))); };
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
      liveRef.current = await connectLive(request.bridgeUrl, {
        engine: request.engine, bundleId: request.bundleId, opponentBundleId: request.opponentBundleId,
        engineId: request.engineId, playerBundleId: request.playerBundleId, nativeOpponentBundleId: request.nativeOpponentBundleId,
      }, applyLiveSnapshot, setLiveStatus, setError);
      setLiveEngine(liveRef.current.engine);
    } catch (caught) { setLiveStatus("error"); setError(caught instanceof Error ? caught.message : "ライブ接続に失敗しました"); }
  };
  const loadFile = async (file: File | undefined) => {
    if (!file) return; disconnectLive(); setError(null); setPlaying(false);
    try { const next = await readReplayFile(file); setReplay(next); setFrameIndex(0); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "リプレイの読み込みに失敗しました"); }
  };

  return <main className="app-shell">
    <header className="topbar"><div><h1>BLACK Battle Studio</h1><p>Decision IDE · {replay.replayId} · {frameLabel} · ライブ {liveStatusJa(liveStatus)}</p></div><div className="top-actions"><input ref={fileRef} className="file-input" type="file" accept="application/json,.json" onChange={(event) => void loadFile(event.target.files?.[0])} /><button type="button" onClick={() => fileRef.current?.click()}>リプレイを開く</button><button type="button" onClick={() => { disconnectLive(); setReplay(demoReplay); setFrameIndex(0); setPlaying(false); setError(null); }}>デモ</button></div></header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <EngineConsole liveStatus={liveStatus} liveEngine={liveEngine} legalSelectionCount={legalSelections.length} onStart={(request) => void startEngine(request)} onStep={() => liveRef.current?.step(legalSelections[0] ?? [0])} onDisconnect={disconnectLive} onError={setError} />
    <NativeRuntimePanel liveStatus={liveStatus} onStart={(request) => void startEngine(request)} onError={setError} />
    <DecisionIDE replay={replay} frame={frame} frameIndex={frameIndex} onSelectFrame={selectFrame} onSelectCard={setSelectedCard} />
    <section className="controls" aria-label="リプレイ操作"><div className="control-buttons"><button type="button" onClick={() => selectFrame(0)} disabled={frameIndex === 0}>⏮</button><button type="button" onClick={() => selectFrame(frameIndex - 1)} disabled={frameIndex === 0}>◀</button><button className="primary" type="button" onClick={() => setPlaying((value) => !value)}>{playing ? "一時停止" : "再生"}</button><button type="button" onClick={() => selectFrame(frameIndex + 1)} disabled={frameIndex === replay.frames.length - 1}>▶</button><button type="button" onClick={() => selectFrame(replay.frames.length - 1)} disabled={frameIndex === replay.frames.length - 1}>⏭</button></div><label className="timeline-label">フレーム {Math.min(frameIndex + 1, replay.frames.length)}/{replay.frames.length}<input type="range" min="0" max={Math.max(0, replay.frames.length - 1)} value={Math.min(frameIndex, replay.frames.length - 1)} onChange={(event) => selectFrame(Number(event.target.value))} style={{ "--progress": `${progress}%` } as CSSProperties} /></label><label className="speed-label">速度<select value={speed} onChange={(event) => setSpeed(Number(event.target.value) as (typeof SPEEDS)[number])}>{SPEEDS.map((value) => <option key={value} value={value}>{value}×</option>)}</select></label></section>
    {selectedCard && <div className="modal-backdrop" role="presentation" onMouseDown={() => setSelectedCard(null)}><section className="card-modal" role="dialog" aria-modal="true" aria-label={selectedCard.name} onMouseDown={(event) => event.stopPropagation()}><button className="close-button" type="button" onClick={() => setSelectedCard(null)}>閉じる</button><CardFace card={selectedCard} /><dl><div><dt>個体</dt><dd>{cardKey(selectedCard)}</dd></div><div><dt>場所</dt><dd>{selectedCard.zone}{selectedCard.slot === null ? "" : ` / ${selectedCard.slot}`}</dd></div><div><dt>進化</dt><dd>{selectedCard.evolution.length ? selectedCard.evolution.join(" → ") : "記録なし"}</dd></div><div><dt>どうぐ</dt><dd>{selectedCard.tools.length ? selectedCard.tools.join(", ") : "なし"}</dd></div></dl></section></div>}
  </main>;
}
