import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { BattleReplay } from "../types";

type Props = {
  replay: BattleReplay;
  frameIndex: number;
  onSeek: (frameIndex: number) => void;
};

const issuePattern = /(MISS|ERROR|FAIL|ILLEGAL|TIMEOUT|CLOCK|NO_BACKUP|NONPERSISTENT|PROMOTION)/i;

function elapsedValues(replay: BattleReplay): number[] {
  return replay.frames.map((frame) => frame.decision?.elapsedMs ?? 0).filter((value) => value > 0).sort((a, b) => a - b);
}

function quantile(values: number[], fraction: number): number {
  if (!values.length) return 1;
  const index = Math.min(values.length - 1, Math.max(0, Math.floor((values.length - 1) * fraction)));
  return Math.max(1, values[index]);
}

export function ReplayTelemetryCanvas({ replay, frameIndex, onSeek }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(900);
  const height = 92;
  const p95 = useMemo(() => quantile(elapsedValues(replay), 0.95), [replay]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const resize = () => setWidth(Math.max(280, host.clientWidth));
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#0a0e14";
    ctx.fillRect(0, 0, width, height);

    const count = replay.frames.length;
    const padX = 12;
    const plotWidth = width - padX * 2;
    const stepWidth = plotWidth / Math.max(1, count);
    replay.frames.forEach((frame, index) => {
      const elapsed = frame.decision?.elapsedMs ?? 0;
      const heat = Math.min(1, elapsed / p95);
      const red = Math.round(68 + heat * 187);
      const green = Math.round(185 - heat * 95);
      const x = padX + index * stepWidth;
      ctx.fillStyle = elapsed > 0 ? `rgb(${red} ${green} 95)` : "#2b3545";
      ctx.fillRect(x, 23, Math.max(1, stepWidth - 1), 34);
      const hasIssue = frame.events.some((event) => issuePattern.test(`${event.type} ${event.text}`));
      if (hasIssue) {
        ctx.fillStyle = "#ff667a";
        ctx.fillRect(x, 13, Math.max(2, stepWidth - 1), 6);
      }
      if (frame.result) {
        ctx.fillStyle = "#8ab4ff";
        ctx.fillRect(x, 61, Math.max(2, stepWidth - 1), 5);
      }
    });

    const markerX = padX + (frameIndex + 0.5) * stepWidth;
    ctx.strokeStyle = "#f4f6f8";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(markerX, 8);
    ctx.lineTo(markerX, 69);
    ctx.stroke();
    ctx.fillStyle = "#98a2b3";
    ctx.font = "600 11px system-ui, sans-serif";
    ctx.textBaseline = "middle";
    ctx.fillText(`FRAME ${frameIndex + 1}/${count}`, 12, 80);
    const timing = replay.frames[frameIndex]?.decision?.elapsedMs;
    const label = timing === null || timing === undefined ? "DECISION —" : `DECISION ${timing.toFixed(1)} ms · P95 ${p95.toFixed(1)} ms`;
    const labelWidth = ctx.measureText(label).width;
    ctx.fillText(label, Math.max(12, width - labelWidth - 12), 80);
  }, [frameIndex, height, p95, replay, width]);

  const seek = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const bounds = canvas.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (event.clientX - bounds.left - 12) / Math.max(1, bounds.width - 24)));
    onSeek(Math.min(replay.frames.length - 1, Math.floor(ratio * replay.frames.length)));
  };

  return (
    <div ref={hostRef} className="telemetry-host">
      <canvas ref={canvasRef} className="telemetry-canvas" onPointerDown={seek} onPointerMove={(event: ReactPointerEvent<HTMLCanvasElement>) => { if (event.buttons === 1) seek(event); }} aria-label="Replay decision-time heatmap" />
      <div className="telemetry-legend"><span><i className="legend-fast" />fast</span><span><i className="legend-slow" />slow</span><span><i className="legend-issue" />issue</span></div>
    </div>
  );
}
