import { cardKey, type BattleFrame, type CardInstance } from "./types";

export function CardFace({ card, compact = false, onSelect }: { card: CardInstance | null; compact?: boolean; onSelect?: (card: CardInstance) => void }) {
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

export function BattleBoard({ frame, onSelect }: { frame: BattleFrame; onSelect: (card: CardInstance) => void }) {
  return <div className="battle-column">
    <PlayerBoard frame={frame} playerIndex={1} onSelect={onSelect} />
    <div className="center-line"><span>{frame.stadium ? `スタジアム: ${frame.stadium.name}` : "スタジアムなし"}</span><strong>ターン {frame.turn}</strong></div>
    <PlayerBoard frame={frame} playerIndex={0} onSelect={onSelect} />
  </div>;
}
