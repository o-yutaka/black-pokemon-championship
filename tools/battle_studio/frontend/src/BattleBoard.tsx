import { useEffect, useState } from "react";
import { cardArtUrl, type CardArtCatalog } from "./cardArt";
import { energyJa, phaseJa } from "./locale";
import { cardKey, type BattleFrame, type CardInstance } from "./types";
import "./all-cards-ui.css";

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

function allVisibleCards(frame: BattleFrame): CardInstance[] {
  const cards: CardInstance[] = [];
  if (frame.stadium) cards.push(frame.stadium);
  for (const player of frame.players) {
    if (player.active) cards.push(player.active);
    cards.push(...player.bench, ...player.hand, ...player.discard);
  }
  return cards;
}

function findCard(frame: BattleFrame, key: string | null): CardInstance | null {
  if (!key) return null;
  return allVisibleCards(frame).find((card) => cardKey(card) === key) ?? null;
}

function inferActionFx(previous: BattleFrame | null, frame: BattleFrame): ActionFx | null {
  if (!previous || previous.frameId === frame.frameId) return null;
  const events = frame.events.slice(previous.events.length);
  const text = events.map((event) => `${event.type} ${event.text}`.toLowerCase()).join(" ");
  const before = new Map(allVisibleCards(previous).map((card) => [cardKey(card), card]));
  const after = new Map(allVisibleCards(frame).map((card) => [cardKey(card), card]));
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
      {!showImage && <><span>{card.name.slice(0, 2)}</span><div className="card-glass"><span>CARD</span><b>{card.name}</b></div></>}
    </div>
    <div className="card-readout">
      <div className="hp-readout"><strong>HP {hpText}</strong><span>{card.damage > 0 ? `${card.damage}ダメージ` : "準備完了"}</span></div>
      <div className="hp-track"><i style={{ width: `${ratio * 100}%` }} /></div>
      <div className="energy-row">{card.energies.length ? card.energies.map((energy, index) => <span key={`${energy}-${index}`} className={`energy-chip energy-${energy.toLowerCase()}`} title={`${energyJa(energy)}エネルギー`}>{energyJa(energy).slice(0, 1)}</span>) : <span className="muted">エネルギーなし</span>}</div>
      {card.tools.length > 0 && <div className="attachment-row" aria-label="ポケモンのどうぐ">{card.tools.map((tool, index) => <span key={`${tool}-${index}`}>どうぐ: {tool}</span>)}</div>}
      {card.evolution.length > 0 && <div className="evolution-stack" aria-label={`進化元 ${card.evolution.length}枚`}>{card.evolution.map((cardId, index) => { const image = catalog.get(cardId); return image ? <img key={`${cardId}-${index}`} src={image} alt="進化元カード" loading="lazy" decoding="async" /> : <span key={`${cardId}-${index}`}>進化元</span>; })}</div>}
      {card.status.length > 0 && <div className="status-row">{card.status.join(" · ")}</div>}
    </div>
  </button>;
}

function CountOrb({ label, value }: { label: string; value: number }) {
  return <div className="count-orb"><strong>{value}</strong><span>{label}</span></div>;
}

function PlayerInfo({ frame, playerIndex, marker }: { frame: BattleFrame; playerIndex: 0 | 1; marker: string }) {
  const player = frame.players[playerIndex];
  const acting = playerIndex === frame.actingPlayer;
  return <div className="player-strip" data-board-marker={marker}>
    <div className="player-identity"><span className="player-dot" /><div><strong>{player.name}</strong><span>{acting ? "思考・行動中" : "待機中"}</span></div></div>
    <div className="counts"><CountOrb label="手札" value={player.handCount} /><CountOrb label="山札" value={player.deckCount} /><CountOrb label="サイド" value={player.prizeCount} /></div>
  </div>;
}

function CardBack({ label, count }: { label: string; count: number }) {
  return <div className="card-back-stack" aria-label={`${label} ${count}枚`}><div className="card-back"><span>BLACK</span><b>{label}</b></div><strong>{count}</strong></div>;
}

function FaceUpZone({ label, cards, onSelect, catalog, marker }: { label: string; cards: CardInstance[]; onSelect: (card: CardInstance) => void; catalog: CardArtCatalog; marker: string }) {
  return <section className="visible-zone" data-board-marker={marker}>
    <header><strong>{label}</strong><span>{cards.length}枚</span></header>
    {cards.length ? <div className="zone-card-strip">{cards.map((card) => <CardFace key={cardKey(card)} card={card} compact onSelect={onSelect} catalog={catalog} />)}</div> : <div className="zone-empty">なし</div>}
  </section>;
}

function ZoneShelf({ frame, playerIndex, isSelf, onSelect, catalog, marker }: { frame: BattleFrame; playerIndex: 0 | 1; isSelf: boolean; onSelect: (card: CardInstance) => void; catalog: CardArtCatalog; marker: string }) {
  const player = frame.players[playerIndex];
  return <div className={`zone-shelf ${isSelf ? "self-zones" : "opponent-zones"}`} data-board-marker={marker}>
    <div className="hidden-zone-row"><CardBack label="山札" count={player.deckCount} /><CardBack label="サイド" count={player.prizeCount} />{!isSelf && <CardBack label="手札" count={player.handCount} />}</div>
    {isSelf && <FaceUpZone label="手札" cards={player.hand} onSelect={onSelect} catalog={catalog} marker={`${marker}-hand`} />}
    <FaceUpZone label="トラッシュ" cards={player.discard} onSelect={onSelect} catalog={catalog} marker={`${marker}-discard`} />
  </div>;
}

function BenchArea({ frame, playerIndex, onSelect, catalog, targetKey, marker }: { frame: BattleFrame; playerIndex: 0 | 1; onSelect: (card: CardInstance) => void; catalog: CardArtCatalog; targetKey: string | null; marker: string }) {
  const player = frame.players[playerIndex];
  const slots = player.bench.length > 5 ? 8 : 5;
  return <div className="bench-area" data-board-marker={marker}>
    <div className="bench-label">ベンチ {player.bench.length}/{slots}</div>
    <div className={`bench-row ${slots === 8 ? "bench-eight" : "bench-five"}`}>{Array.from({ length: slots }, (_, index) => { const boardCard = player.bench[index] ?? null; return <CardFace key={index} card={boardCard} compact onSelect={onSelect} catalog={catalog} highlight={boardCard ? cardKey(boardCard) === targetKey : false} />; })}</div>
  </div>;
}

function ActiveArea({ frame, playerIndex, onSelect, catalog, targetKey, marker }: { frame: BattleFrame; playerIndex: 0 | 1; onSelect: (card: CardInstance) => void; catalog: CardArtCatalog; targetKey: string | null; marker: string }) {
  const player = frame.players[playerIndex];
  return <div className="active-stage" data-board-marker={marker}><div className="active-ring"><span>バトル場</span><CardFace card={player.active} onSelect={onSelect} catalog={catalog} highlight={player.active ? cardKey(player.active) === targetKey : false} /></div></div>;
}

function PlayerBoard({ frame, playerIndex, side, onSelect, catalog, fx }: { frame: BattleFrame; playerIndex: 0 | 1; side: "opponent" | "self"; onSelect: (card: CardInstance) => void; catalog: CardArtCatalog; fx: ActionFx | null }) {
  const player = frame.players[playerIndex];
  const acting = playerIndex === frame.actingPlayer;
  const targetKey = fx?.targetKey ?? null;
  const info = <PlayerInfo frame={frame} playerIndex={playerIndex} marker={`${side}-info`} />;
  const zones = <ZoneShelf frame={frame} playerIndex={playerIndex} isSelf={side === "self"} onSelect={onSelect} catalog={catalog} marker={`${side}-zones`} />;
  const bench = <BenchArea frame={frame} playerIndex={playerIndex} onSelect={onSelect} catalog={catalog} targetKey={targetKey} marker={`${side}-bench`} />;
  const active = <ActiveArea frame={frame} playerIndex={playerIndex} onSelect={onSelect} catalog={catalog} targetKey={targetKey} marker={`${side}-active`} />;

  return <section className={`player-board player-${playerIndex} side-${side} ${acting ? "acting" : "waiting"}`} aria-label={`${player.name}の盤面`}>
    {side === "opponent" ? <>{info}{zones}{bench}{active}</> : <>{active}{bench}{zones}{info}</>}
  </section>;
}

function StadiumArea({ stadium, onSelect, catalog }: { stadium: CardInstance | null; onSelect: (card: CardInstance) => void; catalog: CardArtCatalog }) {
  return <div className="stadium-zone" data-board-marker="stadium"><span>スタジアム</span>{stadium ? <CardFace card={stadium} compact onSelect={onSelect} catalog={catalog} /> : <div className="stadium-empty">なし</div>}</div>;
}

function ActionLayer({ fx, mode }: { fx: ActionFx | null; mode: MotionMode }) {
  if (!fx || mode === "lite") return null;
  return <div className={`action-fx action-${fx.kind} motion-${mode}`} aria-live="polite"><div className="action-line" /><div className="action-orb">{fx.kind === "energy" ? "⚡" : fx.kind === "attack" ? "✦" : fx.kind === "evolve" ? "▲" : "●"}</div><div className="action-caption"><strong>{fx.label}</strong>{fx.value && <span>{fx.value}</span>}</div></div>;
}

export function BattleBoard({ frame, previousFrame, onSelect, catalog, motionMode }: { frame: BattleFrame; previousFrame: BattleFrame | null; onSelect: (card: CardInstance) => void; catalog: CardArtCatalog; motionMode: MotionMode }) {
  const fx = inferActionFx(previousFrame, frame);
  return <div className={`battle-column pocket-board motion-${motionMode}`}><div className="playmat-grid" aria-hidden="true" /><PlayerBoard frame={frame} playerIndex={1} side="opponent" onSelect={onSelect} catalog={catalog} fx={fx} /><div className="center-line" data-board-marker="center"><span>{phaseJa(frame.phase)}</span><StadiumArea stadium={frame.stadium} onSelect={onSelect} catalog={catalog} /><strong>ターン {frame.turn}</strong></div><PlayerBoard frame={frame} playerIndex={0} side="self" onSelect={onSelect} catalog={catalog} fx={fx} /><ActionLayer fx={fx} mode={motionMode} /></div>;
}

export function selectedCardWithArt(card: CardInstance, catalog: CardArtCatalog): CardInstance {
  return card.imageUrl ? card : { ...card, imageUrl: catalog.get(card.cardId) ?? null };
}

export function actionFxDebug(previous: BattleFrame | null, frame: BattleFrame): string | null {
  const fx = inferActionFx(previous, frame);
  const target = fx ? findCard(frame, fx.targetKey)?.name ?? fx.targetKey : null;
  return fx ? `${fx.kind}:${fx.label}:${target ?? "なし"}` : null;
}
