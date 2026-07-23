import type { BattleFrame, CardInstance } from "../types";

export type Rect = { x: number; y: number; width: number; height: number };

export type CanvasCardNode = {
  key: string;
  playerIndex: 0 | 1;
  zone: "active" | "bench";
  slot: number;
  rect: Rect;
  card: CardInstance;
};

export type PlayerBand = {
  playerIndex: 0 | 1;
  rect: Rect;
  header: Rect;
};

export type BoardLayout = {
  width: number;
  height: number;
  cardNodes: CanvasCardNode[];
  playerBands: [PlayerBand, PlayerBand];
  centerLine: Rect;
};

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

export function cardInstanceKey(card: CardInstance): string {
  return `${card.playerIndex}:${card.serial}`;
}

function bandLayout(width: number, y: number, bandHeight: number, playerIndex: 0 | 1): PlayerBand {
  const pad = clamp(width * 0.018, 10, 22);
  const headerHeight = clamp(bandHeight * 0.16, 34, 52);
  return {
    playerIndex,
    rect: { x: pad, y, width: width - pad * 2, height: bandHeight },
    header: { x: pad, y, width: width - pad * 2, height: headerHeight },
  };
}

function addPlayerCards(layout: BoardLayout, frame: BattleFrame, band: PlayerBand): void {
  const player = frame.players[band.playerIndex];
  const pad = clamp(layout.width * 0.018, 10, 22);
  const gap = clamp(layout.width * 0.009, 5, 12);
  const innerX = band.rect.x + pad;
  const innerWidth = band.rect.width - pad * 2;
  const cardWidth = (innerWidth - gap * 4) / 5;
  const headerBottom = band.header.y + band.header.height;
  const benchHeight = clamp(band.rect.height * 0.34, 72, 132);
  const activeHeight = clamp(band.rect.height * 0.39, 96, 158);
  const benchY = band.playerIndex === 1
    ? headerBottom + gap
    : band.rect.y + band.rect.height - benchHeight - gap;
  const activeY = band.playerIndex === 1
    ? benchY + benchHeight + gap
    : headerBottom + gap;
  const activeWidth = clamp(cardWidth * 1.34, 130, 230);
  const activeX = band.rect.x + (band.rect.width - activeWidth) / 2;

  player.bench.slice(0, 5).forEach((card, slot) => {
    layout.cardNodes.push({
      key: cardInstanceKey(card),
      playerIndex: band.playerIndex,
      zone: "bench",
      slot,
      card,
      rect: { x: innerX + slot * (cardWidth + gap), y: benchY, width: cardWidth, height: benchHeight },
    });
  });

  if (player.active) {
    layout.cardNodes.push({
      key: cardInstanceKey(player.active),
      playerIndex: band.playerIndex,
      zone: "active",
      slot: 0,
      card: player.active,
      rect: { x: activeX, y: activeY, width: activeWidth, height: activeHeight },
    });
  }
}

export function computeBattleLayout(width: number, height: number, frame: BattleFrame): BoardLayout {
  const safeWidth = Math.max(320, width);
  const safeHeight = Math.max(480, height);
  const centerHeight = clamp(safeHeight * 0.075, 42, 64);
  const bandHeight = (safeHeight - centerHeight) / 2;
  const opponentBand = bandLayout(safeWidth, 0, bandHeight, 1);
  const playerBand = bandLayout(safeWidth, bandHeight + centerHeight, bandHeight, 0);
  const layout: BoardLayout = {
    width: safeWidth,
    height: safeHeight,
    cardNodes: [],
    playerBands: [playerBand, opponentBand],
    centerLine: { x: 0, y: bandHeight, width: safeWidth, height: centerHeight },
  };
  addPlayerCards(layout, frame, opponentBand);
  addPlayerCards(layout, frame, playerBand);
  return layout;
}

export function hitTestCard(layout: BoardLayout, x: number, y: number): CardInstance | null {
  for (let index = layout.cardNodes.length - 1; index >= 0; index -= 1) {
    const node = layout.cardNodes[index];
    const { rect } = node;
    if (x >= rect.x && x <= rect.x + rect.width && y >= rect.y && y <= rect.y + rect.height) {
      return node.card;
    }
  }
  return null;
}
