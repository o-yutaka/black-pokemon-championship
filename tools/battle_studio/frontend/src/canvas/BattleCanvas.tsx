import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { cardKey, type BattleFrame, type CardInstance } from "../types";
import { computeBattleLayout, hitTestCard, type BoardLayout, type CanvasCardNode, type Rect } from "./layout";

export type CanvasRenderStats = {
  frameMs: number;
  width: number;
  height: number;
  dpr: number;
  cardCount: number;
};

type Props = {
  frame: BattleFrame;
  onSelect: (card: CardInstance) => void;
  onRenderStats?: (stats: CanvasRenderStats) => void;
};

const palette = {
  background: "#080b10",
  panel: "#111722",
  panelActing: "#182233",
  line: "#344054",
  text: "#f3f5f8",
  muted: "#98a2b3",
  accent: "#8ab4ff",
  good: "#42d392",
  warn: "#f5b942",
  bad: "#ff667a",
};

function roundedRect(ctx: CanvasRenderingContext2D, rect: Rect, radius: number): void {
  const r = Math.min(radius, rect.width / 2, rect.height / 2);
  ctx.beginPath();
  ctx.roundRect(rect.x, rect.y, rect.width, rect.height, r);
}

function fitText(ctx: CanvasRenderingContext2D, value: string, maxWidth: number): string {
  if (ctx.measureText(value).width <= maxWidth) return value;
  let candidate = value;
  while (candidate.length > 1 && ctx.measureText(`${candidate}…`).width > maxWidth) candidate = candidate.slice(0, -1);
  return `${candidate}…`;
}

function drawPlayerHeader(ctx: CanvasRenderingContext2D, frame: BattleFrame, playerIndex: 0 | 1, rect: Rect): void {
  const player = frame.players[playerIndex];
  const acting = frame.actingPlayer === playerIndex;
  ctx.fillStyle = acting ? palette.accent : palette.text;
  ctx.font = "700 16px system-ui, sans-serif";
  ctx.textBaseline = "middle";
  ctx.fillText(`${player.name}${acting ? " · ACTING" : ""}`, rect.x + 12, rect.y + rect.height / 2);
  ctx.fillStyle = palette.muted;
  ctx.font = "600 12px system-ui, sans-serif";
  const counts = `HAND ${player.handCount}   DECK ${player.deckCount}   PRIZE ${player.prizeCount}`;
  const width = ctx.measureText(counts).width;
  ctx.fillText(counts, rect.x + rect.width - width - 12, rect.y + rect.height / 2);
}

function drawEnergy(ctx: CanvasRenderingContext2D, node: CanvasCardNode): void {
  const energies = node.card.energies.slice(0, 8);
  const size = Math.max(7, Math.min(11, node.rect.width * 0.065));
  const startX = node.rect.x + 10;
  const y = node.rect.y + node.rect.height - 15;
  energies.forEach((energy, index) => {
    const x = startX + index * (size + 4);
    ctx.beginPath();
    ctx.arc(x, y, size / 2, 0, Math.PI * 2);
    ctx.fillStyle = "#0b0f15";
    ctx.fill();
    ctx.strokeStyle = palette.muted;
    ctx.stroke();
    ctx.fillStyle = palette.text;
    ctx.font = `700 ${Math.max(7, size - 2)}px system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText((energy[0] ?? "?").toUpperCase(), x, y + 0.5);
  });
  ctx.textAlign = "left";
}

function drawCard(ctx: CanvasRenderingContext2D, node: CanvasCardNode): void {
  const active = node.zone === "active";
  const gradient = ctx.createLinearGradient(node.rect.x, node.rect.y, node.rect.x + node.rect.width, node.rect.y + node.rect.height);
  gradient.addColorStop(0, active ? "#24344e" : "#202736");
  gradient.addColorStop(1, "#10151e");
  roundedRect(ctx, node.rect, active ? 16 : 12);
  ctx.fillStyle = gradient;
  ctx.fill();
  ctx.strokeStyle = active ? palette.accent : palette.line;
  ctx.lineWidth = active ? 2 : 1;
  ctx.stroke();

  const pad = Math.max(8, node.rect.width * 0.06);
  ctx.fillStyle = palette.muted;
  ctx.font = `${Math.max(9, Math.min(12, node.rect.width * 0.075))}px ui-monospace, monospace`;
  ctx.textBaseline = "top";
  ctx.fillText(`#${node.card.cardId} · ${node.key}`, node.rect.x + pad, node.rect.y + pad);

  ctx.fillStyle = palette.text;
  ctx.font = `700 ${Math.max(11, Math.min(active ? 19 : 15, node.rect.width * 0.11))}px system-ui, sans-serif`;
  const labelY = node.rect.y + pad + 22;
  ctx.fillText(fitText(ctx, node.card.name, node.rect.width - pad * 2), node.rect.x + pad, labelY);

  const hpKnown = node.card.hp !== null && node.card.maxHp !== null && node.card.maxHp > 0;
  const hpRatio = hpKnown ? Math.max(0, Math.min(1, node.card.hp! / node.card.maxHp!)) : 0;
  const bar = { x: node.rect.x + pad, y: node.rect.y + node.rect.height - 42, width: node.rect.width - pad * 2, height: 7 };
  roundedRect(ctx, bar, 4);
  ctx.fillStyle = "#303948";
  ctx.fill();
  if (hpKnown) {
    roundedRect(ctx, { ...bar, width: Math.max(0, bar.width * hpRatio) }, 4);
    ctx.fillStyle = hpRatio <= 0.25 ? palette.bad : hpRatio <= 0.5 ? palette.warn : palette.good;
    ctx.fill();
  }
  ctx.fillStyle = palette.text;
  ctx.font = "600 11px system-ui, sans-serif";
  ctx.fillText(hpKnown ? `HP ${node.card.hp}/${node.card.maxHp}` : "HP ?", bar.x, bar.y - 16);
  if (node.card.damage > 0) {
    const damage = `${node.card.damage} dmg`;
    const damageWidth = ctx.measureText(damage).width;
    ctx.fillStyle = palette.bad;
    ctx.fillText(damage, bar.x + bar.width - damageWidth, bar.y - 16);
  }
  drawEnergy(ctx, node);
}

function drawBoard(ctx: CanvasRenderingContext2D, frame: BattleFrame, layout: BoardLayout): void {
  ctx.clearRect(0, 0, layout.width, layout.height);
  const bg = ctx.createLinearGradient(0, 0, 0, layout.height);
  bg.addColorStop(0, "#111722");
  bg.addColorStop(0.5, palette.background);
  bg.addColorStop(1, "#111722");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, layout.width, layout.height);

  for (const band of layout.playerBands) {
    roundedRect(ctx, band.rect, 18);
    ctx.fillStyle = frame.actingPlayer === band.playerIndex ? palette.panelActing : palette.panel;
    ctx.fill();
    ctx.strokeStyle = "#242b37";
    ctx.stroke();
    drawPlayerHeader(ctx, frame, band.playerIndex, band.header);
  }

  ctx.fillStyle = "#090c11";
  ctx.fillRect(layout.centerLine.x, layout.centerLine.y, layout.centerLine.width, layout.centerLine.height);
  ctx.strokeStyle = "#252d39";
  ctx.beginPath();
  ctx.moveTo(0, layout.centerLine.y);
  ctx.lineTo(layout.width, layout.centerLine.y);
  ctx.moveTo(0, layout.centerLine.y + layout.centerLine.height);
  ctx.lineTo(layout.width, layout.centerLine.y + layout.centerLine.height);
  ctx.stroke();
  ctx.fillStyle = palette.muted;
  ctx.font = "600 12px system-ui, sans-serif";
  ctx.textBaseline = "middle";
  ctx.fillText(frame.stadium ? `STADIUM · ${frame.stadium.name}` : "NO STADIUM", 16, layout.centerLine.y + layout.centerLine.height / 2);
  ctx.fillStyle = palette.text;
  ctx.font = "800 14px system-ui, sans-serif";
  const turnText = `TURN ${frame.turn} · ${frame.phase.toUpperCase()}`;
  const turnWidth = ctx.measureText(turnText).width;
  ctx.fillText(turnText, layout.width - turnWidth - 16, layout.centerLine.y + layout.centerLine.height / 2);

  layout.cardNodes.forEach((node) => drawCard(ctx, node));
}

export function BattleCanvas({ frame, onSelect, onRenderStats }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const layoutRef = useRef<BoardLayout | null>(null);
  const [size, setSize] = useState({ width: 960, height: 720 });

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const resize = () => {
      const width = Math.max(320, host.clientWidth);
      const height = Math.max(520, Math.min(820, width * 0.76));
      setSize((current) => current.width === width && current.height === height ? current : { width, height });
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    return () => observer.disconnect();
  }, []);

  const accessibleCards = useMemo(() => frame.players.flatMap((player) => [player.active, ...player.bench].filter((card): card is CardInstance => card !== null)), [frame]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    canvas.width = Math.round(size.width * dpr);
    canvas.height = Math.round(size.height * dpr);
    canvas.style.width = `${size.width}px`;
    canvas.style.height = `${size.height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const started = performance.now();
    const layout = computeBattleLayout(size.width, size.height, frame);
    layoutRef.current = layout;
    drawBoard(ctx, frame, layout);
    onRenderStats?.({ frameMs: performance.now() - started, width: size.width, height: size.height, dpr, cardCount: layout.cardNodes.length });
  }, [frame, onRenderStats, size]);

  const selectAtPointer = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    const layout = layoutRef.current;
    if (!canvas || !layout) return;
    const bounds = canvas.getBoundingClientRect();
    const x = (event.clientX - bounds.left) * (layout.width / bounds.width);
    const y = (event.clientY - bounds.top) * (layout.height / bounds.height);
    const card = hitTestCard(layout, x, y);
    if (card) onSelect(card);
  };

  return (
    <div ref={hostRef} className="canvas-board-host">
      <canvas ref={canvasRef} className="battle-canvas" onPointerDown={selectAtPointer} role="img" aria-label={`Turn ${frame.turn} battle board`} />
      <div className="canvas-a11y-list" aria-label="Cards on board">
        {accessibleCards.map((card) => <button key={cardKey(card)} type="button" onClick={() => onSelect(card)}>{card.name}</button>)}
      </div>
    </div>
  );
}
