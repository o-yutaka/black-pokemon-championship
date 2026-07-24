import { useEffect, useMemo, useRef, useState } from "react";
import { demoReplay } from "./demo";
import { EngineConsole, type EngineStartRequest } from "./EngineConsole";
import { connectLive, type LiveConnection, type LiveSnapshot, type LiveStatus } from "./live";
import { liveStatusJa } from "./locale";
import { NativeRuntimePanel } from "./NativeRuntimePanel";
import { readReplayFile } from "./replay";
import { cardKey, type BattleFrame, type BattleReplay, type CardInstance } from "./types";
import "./styles.css";

const SPEEDS = [0.25, 0.5, 1, 2, 4] as const;

function CardFace({ card, compact = false, onSelect }: { card: CardInstance | null; compact?: boolean; onSelect?: (card: CardInstance) => void }) {
  if (!card) return <div className={`card-face empty ${compact ? "compact" : ""}`}>空き</div>;
  const hpText = card.hp === null || card.maxHp === null ? "HP 不明" : `HP ${card.hp}/${card.maxHp}`;
  return <button className={`card-face ${compact ? "compact" : ""}`} type="button" onClick={() => onSelect?.(card)} aria-label={`${card.name}、${hpText}`}>
    <div className="card-id">#{card.cardId} · {cardKey(card)}</div><strong>{card.name}</strong>
    <div className="hp-row"><span>{hpText}</span><span>{card.damage > 0 ? `${card.damage}ダメージ` : "ダメージなし"}</span></div>
    <div className="energy-row">{card.energies.length ? card.energies.map((energy, index) => <span key={`${energy}-${index}`} className="energy-chip">{energy.slice(0, 1)}</span>) : <span className="muted">エネルギーなし</span>}</div>
    {card.status.length > 0 && <div className="status-row">{card.status.join(" · ")}</div>}
  </button>;
}

function PlayerBoard({ frame, playerIndex, onSelect }: { frame: BattleFrame; playerIndex: 0 | 1; onSelect: (card: CardInstance) => void }) {
  const player = frame.players[playerIndex];
  const opponent = playerIndex !== frame.actingPlayer;
  return <section className={`player-board ${opponent ? "opponent" : "acting"}`} aria-label={`${player.name}の盤面`}>
    <div className="player-strip"><div><strong>{player.name}</strong><span>{frame.actingPlayer === playerIndex ? " · 行動中" : ""}</span></div><div className="counts"><span>手札 {player.handCount}</span><span>山札 {player.deckCount}</span><span>サイド {player.prizeCount}</span></div></div>
    <div className="bench-row">{Array.from({ length: 5 }, (_, index) => <CardFace key={index} card={player.bench[index] ?? null} compact onSelect={onSelect} />)}</div>
    <div className="active-row"><div className="zone-label">バトル場</div><CardFace card={player.active} onSelect={onSelect} /></div>
  </section>;
}

function DecisionInspector({ frame }: { frame: BattleFrame }) {
  const decision = frame.decision;
  return <aside className="inspector"><h2>判断</h2>
    {!decision ? <p className="muted">このフレームには判断ログがありません。</p> : <><div className="decision-summary"><span className="badge">{decision.goal}</span><strong>{decision.chosen}</strong><span>{decision.confidence === null ? "信頼度 —" : `信頼度 ${(decision.confidence * 100).toFixed(0)}%`}</span><span>{decision.elapsedMs === null ? "思考時間 —" : `${decision.elapsedMs.toFixed(0)} ms`}</span></div><ol className="candidate-list">{decision.candidates.slice().sort((a, b) => b.score - a.score).map((candidate) => <li key={`${candidate.label}-${candidate.score}`} className={candidate.selected ? "selected" : ""}><span>{candidate.label}</span><strong>{candidate.score.toFixed(2)}</strong></li>)}</ol></>}
    <h2>イベント</h2><div className="event-log">{frame.events.length ? frame.events.map((event, index) => <div key={`${event.type}-${index}`}><span>{event.type}</span><p>{event.text}</p></div>) : <p className="muted">イベントはありません。</p>}</div>
  </aside>;
}

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
    <header className="topbar"><div><h1>BLACK Battle Studio</h1><p>{replay.replayId} · {frameLabel} · ライブ {liveStatusJa(liveStatus)}</p></div><div className="top-actions"><input ref={fileRef} className="file-input" type="file" accept="application/json,.json" onChange={(event) => void loadFile(event.target.files?.[0])} /><button type="button" onClick={() => fileRef.current?.click()}>リプレイを開く</button><button type="button" onClick={() => { disconnectLive(); setReplay(demoReplay); setFrameIndex(0); setPlaying(false); setError(null); }}>デモ</button></div></header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <EngineConsole liveStatus={liveStatus} liveEngine={liveEngine} legalSelectionCount={legalSelections.length} onStart={(request) => void startEngine(request)} onStep={() => liveRef.current?.step(legalSelections[0] ?? [0])} onDisconnect={disconnectLive} onError={setError} />
    <NativeRuntimePanel liveStatus={liveStatus} onStart={(request) => void startEngine(request)} onError={setError} />
    <div className="workspace"><div className="battle-column"><PlayerBoard frame={frame} playerIndex={1} onSelect={setSelectedCard} /><div className="center-line"><span>{frame.stadium ? `スタジアム: ${frame.stadium.name}` : "スタジアムなし"}</span><strong>ターン {frame.turn}</strong></div><PlayerBoard frame={frame} playerIndex={0} onSelect={setSelectedCard} /></div><DecisionInspector frame={frame} /></div>
    <section className="controls" aria-label="リプレイ操作"><div className="control-buttons"><button type="button" onClick={() => setFrameIndex(0)} disabled={frameIndex === 0}>⏮</button><button type="button" onClick={() => setFrameIndex((value) => Math.max(0, value - 1))} disabled={frameIndex === 0}>◀</button><button className="primary" type="button" onClick={() => setPlaying((value) => !value)}>{playing ? "一時停止" : "再生"}</button><button type="button" onClick={() => setFrameIndex((value) => Math.min(replay.frames.length - 1, value + 1))} disabled={frameIndex === replay.frames.length - 1}>▶</button><button type="button" onClick={() => setFrameIndex(replay.frames.length - 1)} disabled={frameIndex === replay.frames.length - 1}>⏭</button></div><label className="timeline-label">フレーム {Math.min(frameIndex + 1, replay.frames.length)}/{replay.frames.length}<input type="range" min="0" max={Math.max(0, replay.frames.length - 1)} value={Math.min(frameIndex, replay.frames.length - 1)} onChange={(event) => { setPlaying(false); setFrameIndex(Number(event.target.value)); }} style={{ "--progress": `${progress}%` } as React.CSSProperties} /></label><label className="speed-label">速度<select value={speed} onChange={(event) => setSpeed(Number(event.target.value) as (typeof SPEEDS)[number])}>{SPEEDS.map((value) => <option key={value} value={value}>{value}×</option>)}</select></label></section>
    {selectedCard && <div className="modal-backdrop" role="presentation" onMouseDown={() => setSelectedCard(null)}><section className="card-modal" role="dialog" aria-modal="true" aria-label={selectedCard.name} onMouseDown={(event) => event.stopPropagation()}><button className="close-button" type="button" onClick={() => setSelectedCard(null)}>閉じる</button><CardFace card={selectedCard} /><dl><div><dt>個体</dt><dd>{cardKey(selectedCard)}</dd></div><div><dt>場所</dt><dd>{selectedCard.zone}{selectedCard.slot === null ? "" : ` / ${selectedCard.slot}`}</dd></div><div><dt>進化</dt><dd>{selectedCard.evolution.length ? selectedCard.evolution.join(" → ") : "記録なし"}</dd></div><div><dt>どうぐ</dt><dd>{selectedCard.tools.length ? selectedCard.tools.join(", ") : "なし"}</dd></div></dl></section></div>}
  </main>;
}
