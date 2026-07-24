import { useEffect, useState } from "react";
import { cardArtUrl, type CardArtCatalog } from "./cardArt";
import { energyJa, phaseJa } from "./locale";
import { cardKey, type BattleFrame, type CardInstance } from "./types";

export type MotionMode = "full" | "balanced" | "lite";

type ActionFx = {
  kind: "energy" | "attack" | "evolve" | "switch" | "ability" | "generic";
  actor: number;
  sourceKey: string | null;
  targetKey: string | null;
  label: string;
  value: string | null;
};

function hpRatio(card: CardInstance): number {
  if (card.hp === null || card.maxHp === null || card.maxHp <= 0) return 0;
  return Math.max(0, Math.min(1, card.hp / card.maxHp));
}

function allBoardCards(frame: BattleFrame): CardInstance[] {
  return frame.players.flatMap((player) => [player.active, ...player.bench].filter((card): card is CardInstance => card !== null));
}

function findCard(frame: BattleFrame, key: string | null): CardInstance | null {
  if (!key) return null;
  return allBoardCards(frame).find((card) => cardKey(card) === key) ?? null;
}

function inferActionFx(previous: BattleFrame | null, frame: BattleFrame): ActionFx | null {
  if (!previous || previous.frameId === frame.frameId) return null;
  const events = frame.events.slice(previous.events.length);
  const text = events.map((event) => `${event.type} ${event.text}`.toLowerCase()).join(" ");
  const before = new Map(allBoardCards(previous).map((card) => [cardKey(card), card]));
  const after = new Map(allBoardCards(frame).map((card) => [cardKey(card), card]));
  const actor = frame.decision?.actor ?? frame.actingPlayer;

  for (const [key, card] of after) {
    const old = before.get(key);
    if (old && card.energies.length > old.energies.length) {
      return { kind: "energy", actor, sourceKey: null, targetKey: key, label: "エネルギーをつけた", value: energyJa(card.energies.at(-1) ?? "") };
    }
  }
  for (const [key, card] of after) {
    const old = before.get(key);
    if (old && card.evolution.length > old.evolution.length) {
      return { kind: "evolve", actor, sourceKey: key, targetKey: key, label: "進化", value: card.name };
    }
  }
  const opponent = actor === 0 ? 1 : 0;
  const opponentBefore = previous.players[opponent];
  const opponentAfter = frame.players[opponent];
  const damageDelta = (opponentAfter.active?.damage ?? 0) - (opponentBefore.active?.damage ?? 0);
  if (damageDelta > 0 || /attack|damage|ko|ワザ|攻撃/.test(text)) {
    return { kind: "attack", actor, sourceKey: previous.players[actor].active ? cardKey(previous.players[actor].active!) : null, targetKey: opponentAfter.active ? cardKey(opponentAfter.active) : null, label: "ワザを使った", value: damageDelta > 0 ? `${damageDelta}ダメージ` : null };
  }
  const beforeActive = previous.players[actor].active;
  const afterActive = frame.players[actor].active;
  if (beforeActive && afterActive && cardKey(beforeActive) !== cardKey(afterActive)) {
    return { kind: "switch", actor, sourceKey: cardKey(beforeActive), targetKey: cardKey(afterActive), label: "入れ替え", value: afterActive.name };
  }
  if (/ability|特性/.test(text)) {
    return { kind: "ability", actor, sourceKey: afterActive ? cardKey(afterActive) : null, targetKey: afterActive ? cardKey(afterActive) : null, label: "特性を使った", value: null };
  }
  const last = events.at(-1);
  return last ? { kind: "generic", actor, sourceKey: null, targetKey: last.cardKey, label: "行動", value: last.text } : null;
}

export function CardFace({ card, compact = false, onSelect, catalog, highlight = false }: { card: CardInstance | null; compact?: boolean; onSelect?: (card: CardInstance) => void; catalog: CardArtCatalog; highlight?: boolean }) {
  const resolvedImageUrl = card ? cardArtUrl(card.cardId, card.imageUrl, catalog) : null;
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null);
  useEffect(() => {
    if (resolvedImageUrl !== failedImageUrl) setFailedImageUrl(null);
  }, [resolvedImageUrl]);

  if (!card) return <div className={`card-face empty ${compact ? "compact" : ""}`}><span>＋</span><small>空き枠</small></div>;
  const hpText = card.hp === null || card.maxHp === null ? "HP不明" : `${card.hp}/${card.maxHp}`;
  const ratio = hpRatio(card);
  const critical = ratio > 0 && ratio <= 0.3;
  const showImage = Boolean(resolvedImageUrl && resolvedImageUrl !== failedImageUrl);
  return <button className={`card-face ${compact ? "compact" : ""} ${critical ? "critical" : ""} ${highlight ? "action-target" : ""}`} type="button" onClick={() => onSelect?.(card)} aria-label={`${card.name}、HP ${hpText}`} data-card-key={cardKey(card)}>
    <div className={`card-art ${showImage ? "has-card-image" : "fallback-card-art"}`}>
      {showImage && <img src={resolvedImageUrl!} alt={`${card.name}のカード画像`} loading="lazy" decoding="async" draggable={false} onError={() => setFailedImageUrl(resolvedImageUrl)} />}
      {!showImage && <><span>{card.name.slice(0, 2)}</span><div className="card-glass"><span>#{card.cardId}</span><b>{card.name}</b></div></>}
    </div>
    <div className="card-readout">
      <div className="hp-readout"><strong>HP {hpText}</strong><span>{card.damage > 0 ? `${card.damage}ダメージ` : "準備完了"}</span></div>
      <div className="hp-track"><i style={{ width: `${ratio * 100}%` }} /></div>
      <div className="energy-row">{card.energies.length ? card.energies.map((energy, index) => <span key={`${energy}-${index}`} className={`energy-chip energy-${energy.toLowerCase()}`} title={`${energyJa(energy)}エネルギー`}>{energyJa(energy).slice(0, 1)}</span>) : <span className="muted">エネルギーなし</span>}</div>
      {card.status.length > 0 && <div className="status-row">{card.status.join(" · ")}</div>}
      <small className="card-instance">カード識別 {cardKey(card)}</small>
    </div>
  </button>;
}

function CountOrb({ label, value }: { label: string; value: number }) {
  return <div className="count-orb"><strong>{value}</strong><span>{label}</span></div>;
}

function PlayerBoard({ frame, playerIndex, onSelect, catalog, fx }: { frame: BattleFrame; playerIndex: 0 | 1; onSelect: (card: CardInstance) => void; catalog: CardArtCatalog; fx: ActionFx | null }) {
  const player = frame.players[playerIndex];
  const acting = playerIndex === frame.actingPlayer;
  const targetKey = fx?.targetKey ?? null;
  return <section className={`player-board player-${playerIndex} ${acting ? "acting" : "waiting"}`} aria-label={`${player.name}の盤面`}>
    <div className="player-strip">
      <div className="player-identity"><span className="player-dot" /><div><strong>{player.name}</strong><span>{acting ? "思考・行動中" : "待機中"}</span></div></div>
      <div className="counts"><CountOrb label="手札" value={player.handCount} /><CountOrb label="山札" value={player.deckCount} /><CountOrb label="サイド" value={player.prizeCount} /></div>
    </div>
    <div className="bench-label">ベンチ</div>
    <div className="bench-row">{Array.from({ length: 5 }, (_, index) => { const boardCard = player.bench[index] ?? null; return <CardFace key={index} card={boardCard} compact onSelect={onSelect} catalog={catalog} highlight={boardCard ? cardKey(boardCard) === targetKey : false} />; })}</div>
    <div className="active-stage"><div className="active-ring"><span>バトル場</span><CardFace card={player.active} onSelect={onSelect} catalog={catalog} highlight={player.active ? cardKey(player.active) === targetKey : false} /></div></div>
  </section>;
}

function ActionLayer({ fx, mode }: { fx: ActionFx | null; mode: MotionMode }) {
  if (!fx || mode === "lite") return null;
  return <div className={`action-fx action-${fx.kind} motion-${mode}`} aria-live="polite"><div className="action-line" /><div className="action-orb">{fx.kind === "energy" ? "⚡" : fx.kind === "attack" ? "✦" : fx.kind === "evolve" ? "▲" : "●"}</div><div className="action-caption"><strong>{fx.label}</strong>{fx.value && <span>{fx.value}</span>}</div></div>;
}

export function BattleBoard({ frame, previousFrame, onSelect, catalog, motionMode }: { frame: BattleFrame; previousFrame: BattleFrame | null; onSelect: (card: CardInstance) => void; catalog: CardArtCatalog; motionMode: MotionMode }) {
  const fx = inferActionFx(previousFrame, frame);
  return <div className={`battle-column pocket-board motion-${motionMode}`}><div className="playmat-grid" aria-hidden="true" /><PlayerBoard frame={frame} playerIndex={1} onSelect={onSelect} catalog={catalog} fx={fx} /><div className="center-line"><span>{frame.stadium ? frame.stadium.name : "スタジアムなし"}</span><strong>ターン {frame.turn}</strong><span>{phaseJa(frame.phase)}</span></div><PlayerBoard frame={frame} playerIndex={0} onSelect={onSelect} catalog={catalog} fx={fx} /><ActionLayer fx={fx} mode={motionMode} /></div>;
}

export function selectedCardWithArt(card: CardInstance, catalog: CardArtCatalog): CardInstance {
  return card.imageUrl ? card : { ...card, imageUrl: catalog.get(card.cardId) ?? null };
}

export function actionFxDebug(previous: BattleFrame | null, frame: BattleFrame): string | null {
  const fx = inferActionFx(previous, frame);
  const target = fx ? findCard(frame, fx.targetKey)?.name ?? fx.targetKey : null;
  return fx ? `${fx.kind}:${fx.label}:${target ?? "なし"}` : null;
}
