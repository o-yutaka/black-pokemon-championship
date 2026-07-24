import { cardKey, type BattleFrame, type CardInstance } from "./types";

function hpRatio(card: CardInstance): number {
  if (card.hp === null || card.maxHp === null || card.maxHp <= 0) return 0;
  return Math.max(0, Math.min(1, card.hp / card.maxHp));
}

export function CardFace({ card, compact = false, onSelect }: { card: CardInstance | null; compact?: boolean; onSelect?: (card: CardInstance) => void }) {
  if (!card) return <div className={`card-face empty ${compact ? "compact" : ""}`}><span>＋</span><small>空き枠</small></div>;
  const hpText = card.hp === null || card.maxHp === null ? "HP 不明" : `${card.hp}/${card.maxHp}`;
  const ratio = hpRatio(card);
  const critical = ratio > 0 && ratio <= 0.3;
  return <button className={`card-face ${compact ? "compact" : ""} ${critical ? "critical" : ""}`} type="button" onClick={() => onSelect?.(card)} aria-label={`${card.name}、HP ${hpText}`}>
    <div className="card-art" style={card.imageUrl ? { backgroundImage: `url(${card.imageUrl})` } : undefined}>
      {!card.imageUrl && <span>{card.name.slice(0, 2)}</span>}
      <div className="card-glass"><span>#{card.cardId}</span><b>{card.name}</b></div>
    </div>
    <div className="card-readout">
      <div className="hp-readout"><strong>HP {hpText}</strong><span>{card.damage > 0 ? `${card.damage} DMG` : "READY"}</span></div>
      <div className="hp-track"><i style={{ width: `${ratio * 100}%` }} /></div>
      <div className="energy-row">{card.energies.length ? card.energies.map((energy, index) => <span key={`${energy}-${index}`} className="energy-chip" title={energy}>{energy.slice(0, 1)}</span>) : <span className="muted">エネルギーなし</span>}</div>
      {card.status.length > 0 && <div className="status-row">{card.status.join(" · ")}</div>}
      <small className="card-instance">{cardKey(card)}</small>
    </div>
  </button>;
}

function CountOrb({ label, value }: { label: string; value: number }) {
  return <div className="count-orb"><strong>{value}</strong><span>{label}</span></div>;
}

function PlayerBoard({ frame, playerIndex, onSelect }: { frame: BattleFrame; playerIndex: 0 | 1; onSelect: (card: CardInstance) => void }) {
  const player = frame.players[playerIndex];
  const acting = playerIndex === frame.actingPlayer;
  return <section className={`player-board player-${playerIndex} ${acting ? "acting" : "waiting"}`} aria-label={`${player.name}の盤面`}>
    <div className="player-strip">
      <div className="player-identity"><span className="player-dot" /><div><strong>{player.name}</strong><span>{acting ? "思考・行動中" : "待機中"}</span></div></div>
      <div className="counts"><CountOrb label="手札" value={player.handCount} /><CountOrb label="山札" value={player.deckCount} /><CountOrb label="サイド" value={player.prizeCount} /></div>
    </div>
    <div className="bench-label">BENCH</div>
    <div className="bench-row">{Array.from({ length: 5 }, (_, index) => <CardFace key={index} card={player.bench[index] ?? null} compact onSelect={onSelect} />)}</div>
    <div className="active-stage"><div className="active-ring"><span>ACTIVE</span><CardFace card={player.active} onSelect={onSelect} /></div></div>
  </section>;
}

export function BattleBoard({ frame, onSelect }: { frame: BattleFrame; onSelect: (card: CardInstance) => void }) {
  return <div className="battle-column pocket-board">
    <div className="playmat-grid" aria-hidden="true" />
    <PlayerBoard frame={frame} playerIndex={1} onSelect={onSelect} />
    <div className="center-line"><span>{frame.stadium ? frame.stadium.name : "NO STADIUM"}</span><strong>TURN {frame.turn}</strong><span>{frame.phase}</span></div>
    <PlayerBoard frame={frame} playerIndex={0} onSelect={onSelect} />
  </div>;
}
