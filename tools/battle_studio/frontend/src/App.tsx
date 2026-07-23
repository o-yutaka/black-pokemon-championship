import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type CSSProperties, type MouseEvent } from "react";
import { BattleCanvas, type CanvasRenderStats } from "./canvas/BattleCanvas";
import { ReplayTelemetryCanvas } from "./canvas/ReplayTelemetryCanvas";
import { demoReplay } from "./demo";
import { connectLiveEmulator, type LiveConnection, type LiveSnapshot, type LiveStatus } from "./live";
import { readReplayFile } from "./replay";
import { cardKey, type BattleFrame, type BattleReplay, type CardInstance } from "./types";
import "./styles.css";

const SPEEDS = [0.25, 0.5, 1, 2, 4] as const;
type RenderMode = "canvas" | "dom";

function CardFace({ card, compact = false, onSelect }: { card: CardInstance | null; compact?: boolean; onSelect?: (card: CardInstance) => void }) {
  if (!card) return <div className={`card-face empty ${compact ? "compact" : ""}`}>EMPTY</div>;
  const hpText = card.hp === null || card.maxHp === null ? "HP ?" : `HP ${card.hp}/${card.maxHp}`;
  return (
    <button className={`card-face ${compact ? "compact" : ""}`} type="button" onClick={() => onSelect?.(card)} aria-label={`${card.name}, ${hpText}`}>
      <div className="card-id">#{card.cardId} · {cardKey(card)}</div>
      <strong>{card.name}</strong>
      <div className="hp-row"><span>{hpText}</span><span>{card.damage > 0 ? `${card.damage} dmg` : "clean"}</span></div>
      <div className="energy-row">{card.energies.length ? card.energies.map((energy, index) => <span key={`${energy}-${index}`} className="energy-chip">{energy.slice(0, 1)}</span>) : <span className="muted">No Energy</span>}</div>
      {card.status.length > 0 && <div className="status-row">{card.status.join(" · ")}</div>}
    </button>
  );
}

function PlayerBoard({ frame, playerIndex, onSelect }: { frame: BattleFrame; playerIndex: 0 | 1; onSelect: (card: CardInstance) => void }) {
  const player = frame.players[playerIndex];
  const opponent = playerIndex !== frame.actingPlayer;
  return (
    <section className={`player-board ${opponent ? "opponent" : "acting"}`} aria-label={`${player.name} board`}>
      <div className="player-strip">
        <div><strong>{player.name}</strong><span>{frame.actingPlayer === playerIndex ? " · ACTING" : ""}</span></div>
        <div className="counts"><span>Hand {player.handCount}</span><span>Deck {player.deckCount}</span><span>Prize {player.prizeCount}</span></div>
      </div>
      <div className="bench-row">
        {Array.from({ length: 5 }, (_, index) => <CardFace key={index} card={player.bench[index] ?? null} compact onSelect={onSelect} />)}
      </div>
      <div className="active-row">
        <div className="zone-label">ACTIVE</div>
        <CardFace card={player.active} onSelect={onSelect} />
      </div>
    </section>
  );
}

function DecisionInspector({ frame }: { frame: BattleFrame }) {
  const decision = frame.decision;
  return (
    <aside className="inspector">
      <h2>Decision</h2>
      {!decision ? <p className="muted">No planner trace attached to this frame.</p> : <>
        <div className="decision-summary">
          <span className="badge">{decision.goal}</span>
          <strong>{decision.chosen}</strong>
          <span>{decision.confidence === null ? "confidence —" : `confidence ${(decision.confidence * 100).toFixed(0)}%`}</span>
          <span>{decision.elapsedMs === null ? "time —" : `${decision.elapsedMs.toFixed(0)} ms`}</span>
        </div>
        <ol className="candidate-list">
          {decision.candidates.slice().sort((a, b) => b.score - a.score).map((candidate) => (
            <li key={`${candidate.label}-${candidate.score}`} className={candidate.selected ? "selected" : ""}>
              <span>{candidate.label}</span><strong>{candidate.score.toFixed(2)}</strong>
            </li>
          ))}
        </ol>
      </>}
      <h2>Events</h2>
      <div className="event-log">
        {frame.events.length ? frame.events.map((event, index) => <div key={`${event.type}-${index}`}><span>{event.type}</span><p>{event.text}</p></div>) : <p className="muted">No event attached.</p>}
      </div>
    </aside>
  );
}

export default function App() {
  const [replay, setReplay] = useState<BattleReplay>(demoReplay);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const [selectedCard, setSelectedCard] = useState<CardInstance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<LiveStatus>("disconnected");
  const [legalSelections, setLegalSelections] = useState<number[][]>([]);
  const [renderMode, setRenderMode] = useState<RenderMode>("canvas");
  const [canvasStats, setCanvasStats] = useState<CanvasRenderStats | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const liveRef = useRef<LiveConnection | null>(null);

  const frame = replay.frames[Math.min(frameIndex, replay.frames.length - 1)];
  const progress = replay.frames.length <= 1 ? 0 : (frameIndex / (replay.frames.length - 1)) * 100;

  useEffect(() => {
    if (!playing) return;
    const delay = Math.max(80, 900 / speed);
    const timer = window.setInterval(() => {
      setFrameIndex((current) => {
        if (current >= replay.frames.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, delay);
    return () => window.clearInterval(timer);
  }, [playing, replay.frames.length, speed]);

  useEffect(() => setSelectedCard(null), [frameIndex]);
  useEffect(() => () => liveRef.current?.close(), []);

  const frameLabel = useMemo(() => `Turn ${frame.turn} · ${frame.phase} · Action ${frame.actionCount}`, [frame]);
  const updateCanvasStats = useCallback((next: CanvasRenderStats) => {
    setCanvasStats((current) => current && current.width === next.width && current.height === next.height && current.cardCount === next.cardCount && Math.abs(current.frameMs - next.frameMs) < 0.05 ? current : next);
  }, []);

  const applyLiveSnapshot = (snapshot: LiveSnapshot) => {
    setLegalSelections(snapshot.legalSelections);
    setReplay((current) => {
      const frames = current.replayId === snapshot.sessionId
        ? [...current.frames.filter((item) => item.frameId !== snapshot.frame.frameId), snapshot.frame].sort((a, b) => a.frameId - b.frameId)
        : [snapshot.frame];
      return {
        schemaVersion: "1.0",
        replayId: snapshot.sessionId,
        createdAt: new Date().toISOString(),
        source: "unknown",
        hiddenInformationPolicy: "spectator",
        frames,
      };
    });
    setFrameIndex(snapshot.frame.frameId);
  };

  const connectEmulator = async () => {
    setError(null);
    setPlaying(false);
    liveRef.current?.close();
    try {
      const baseUrl = import.meta.env.VITE_LIVE_BASE_URL || window.location.origin;
      liveRef.current = await connectLiveEmulator(baseUrl, applyLiveSnapshot, setLiveStatus, setError);
    } catch (caught) {
      setLiveStatus("error");
      setError(caught instanceof Error ? caught.message : "Live connection failed");
    }
  };

  const disconnectLive = () => {
    liveRef.current?.close();
    liveRef.current = null;
    setLiveStatus("disconnected");
    setLegalSelections([]);
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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Replay load failed");
    }
  };

  const seek = (value: number) => {
    setPlaying(false);
    setFrameIndex(Math.max(0, Math.min(replay.frames.length - 1, value)));
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div><h1>BLACK Battle Studio</h1><p>{replay.replayId} · {frameLabel} · LIVE {liveStatus.toUpperCase()}</p></div>
        <div className="top-actions">
          <input ref={fileRef} className="file-input" type="file" accept="application/json,.json" onChange={(event: ChangeEvent<HTMLInputElement>) => void loadFile(event.target.files?.[0])} />
          <button type="button" onClick={() => fileRef.current?.click()}>Open Replay</button>
          <button type="button" onClick={() => void connectEmulator()} disabled={liveStatus === "connecting" || liveStatus === "connected"}>Connect Emulator</button>
          <button type="button" onClick={() => liveRef.current?.step(legalSelections[0] ?? [0])} disabled={liveStatus !== "connected" || legalSelections.length === 0}>Live Step</button>
          <button type="button" onClick={disconnectLive} disabled={liveStatus === "disconnected"}>Disconnect</button>
          <button type="button" onClick={() => { disconnectLive(); setReplay(demoReplay); setFrameIndex(0); setPlaying(false); setError(null); }}>Demo</button>
        </div>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}

      <div className="workspace">
        <div className="battle-column">
          <div className="visualizer-toolbar">
            <div className="mode-switch" role="group" aria-label="Battle renderer">
              <button className={renderMode === "canvas" ? "active" : ""} type="button" onClick={() => setRenderMode("canvas")}>Canvas</button>
              <button className={renderMode === "dom" ? "active" : ""} type="button" onClick={() => setRenderMode("dom")}>DOM fallback</button>
            </div>
            <div className="canvas-stats">
              {renderMode === "canvas" && canvasStats ? `${canvasStats.frameMs.toFixed(2)} ms · ${canvasStats.cardCount} cards · DPR ${canvasStats.dpr.toFixed(1)}` : "Snapshot Truth · read only"}
            </div>
          </div>
          {renderMode === "canvas"
            ? <BattleCanvas frame={frame} onSelect={setSelectedCard} onRenderStats={updateCanvasStats} />
            : <div className="dom-board">
                <PlayerBoard frame={frame} playerIndex={1} onSelect={setSelectedCard} />
                <div className="center-line"><span>{frame.stadium ? `Stadium: ${frame.stadium.name}` : "No Stadium"}</span><strong>TURN {frame.turn}</strong></div>
                <PlayerBoard frame={frame} playerIndex={0} onSelect={setSelectedCard} />
              </div>}
        </div>
        <DecisionInspector frame={frame} />
      </div>

      <section className="controls" aria-label="Replay controls">
        <div className="control-buttons">
          <button type="button" onClick={() => seek(0)} disabled={frameIndex === 0}>⏮</button>
          <button type="button" onClick={() => seek(frameIndex - 1)} disabled={frameIndex === 0}>◀</button>
          <button className="primary" type="button" onClick={() => setPlaying((value) => !value)}>{playing ? "Pause" : "Play"}</button>
          <button type="button" onClick={() => seek(frameIndex + 1)} disabled={frameIndex === replay.frames.length - 1}>▶</button>
          <button type="button" onClick={() => seek(replay.frames.length - 1)} disabled={frameIndex === replay.frames.length - 1}>⏭</button>
        </div>
        <div className="timeline-stack">
          <ReplayTelemetryCanvas replay={replay} frameIndex={frameIndex} onSeek={seek} />
          <label className="timeline-label">Frame {frameIndex + 1}/{replay.frames.length}
            <input type="range" min="0" max={replay.frames.length - 1} value={frameIndex} onChange={(event: ChangeEvent<HTMLInputElement>) => seek(Number(event.target.value))} style={{ "--progress": `${progress}%` } as CSSProperties} />
          </label>
        </div>
        <label className="speed-label">Speed
          <select value={speed} onChange={(event: ChangeEvent<HTMLSelectElement>) => setSpeed(Number(event.target.value) as (typeof SPEEDS)[number])}>{SPEEDS.map((value) => <option key={value} value={value}>{value}×</option>)}</select>
        </label>
      </section>

      {selectedCard && <div className="modal-backdrop" role="presentation" onMouseDown={() => setSelectedCard(null)}>
        <section className="card-modal" role="dialog" aria-modal="true" aria-label={selectedCard.name} onMouseDown={(event: MouseEvent<HTMLElement>) => event.stopPropagation()}>
          <button className="close-button" type="button" onClick={() => setSelectedCard(null)}>Close</button>
          <CardFace card={selectedCard} />
          <dl>
            <div><dt>Instance</dt><dd>{cardKey(selectedCard)}</dd></div>
            <div><dt>Zone</dt><dd>{selectedCard.zone}{selectedCard.slot === null ? "" : ` / ${selectedCard.slot}`}</dd></div>
            <div><dt>Evolution</dt><dd>{selectedCard.evolution.length ? selectedCard.evolution.join(" → ") : "None recorded"}</dd></div>
            <div><dt>Tools</dt><dd>{selectedCard.tools.length ? selectedCard.tools.join(", ") : "None"}</dd></div>
          </dl>
        </section>
      </div>}
    </main>
  );
}
