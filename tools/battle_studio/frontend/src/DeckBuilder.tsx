import { useEffect, useMemo, useState } from "react";
import { fetchCards, type CardRecord } from "./studio";

type Props = { catalogVersion: number; importedDeck: number[] };

export function DeckBuilder({ catalogVersion, importedDeck }: Props) {
  const [cards, setCards] = useState<CardRecord[]>([]); const [deck, setDeck] = useState<Map<number, number>>(new Map());
  const [query, setQuery] = useState(""); const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (catalogVersion > 0) void fetchCards().then(setCards).catch((caught) => setError(caught instanceof Error ? caught.message : String(caught))); }, [catalogVersion]);
  useEffect(() => { if (!importedDeck.length) return; const next = new Map<number, number>(); importedDeck.forEach((id) => next.set(id, (next.get(id) || 0) + 1)); setDeck(next); }, [importedDeck]);
  const byId = useMemo(() => new Map(cards.map((card) => [card.cardId, card])), [cards]);
  const total = [...deck.values()].reduce((sum, value) => sum + value, 0);
  const aceCount = [...deck.entries()].reduce((sum, [id, count]) => sum + (byId.get(id)?.aceSpec ? count : 0), 0);
  const basicPokemon = [...deck.entries()].some(([id, count]) => count > 0 && /basic/i.test(byId.get(id)?.stageOrType || "") && !byId.get(id)?.basicEnergy);
  const violations = [total !== 60 && `${total}/60 cards`, aceCount > 1 && `${aceCount} ACE SPEC`, !basicPokemon && "Basic Pokémonなし"].filter(Boolean) as string[];
  const visible = cards.filter((card) => `${card.cardId} ${card.name} ${card.expansion} ${card.stageOrType} ${card.pokemonType}`.toLowerCase().includes(query.toLowerCase())).slice(0, 120);
  const deckRows = [...deck.entries()].filter(([, count]) => count > 0).sort((a, b) => a[0] - b[0]);

  function change(card: CardRecord, delta: number) {
    setDeck((current) => { const next = new Map(current); const now = next.get(card.cardId) || 0; const limit = card.basicEnergy ? 60 : 4; const value = Math.max(0, Math.min(limit, now + delta)); if (value) next.set(card.cardId, value); else next.delete(card.cardId); return next; });
  }
  function decrementUnknown(id: number, count: number) { setDeck((current) => { const next = new Map(current); if (count > 1) next.set(id, count - 1); else next.delete(id); return next; }); }
  function exportDeck() {
    const ids = deckRows.flatMap(([id, count]) => Array.from({ length: count }, () => id));
    const blob = new Blob([`${ids.join("\n")}\n`], { type: "text/csv" }); const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = "deck.csv"; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <section className="deck-builder" aria-label="Deck builder">
    <div className="builder-head"><div><span className="section-kicker">DECK BUILDER</span><h2>カードを選んで60枚構築</h2></div><div className={`deck-verdict ${violations.length ? "hold" : "pass"}`}><strong>{total}/60</strong><span>{violations.length ? violations.join(" · ") : "VALID"}</span></div></div>
    {error && <div className="inline-error">{error}</div>}
    {!cards.length ? <p className="builder-empty">上の「Upload 3 Files」でカードDBを読み込むと構築できる。</p> : <div className="builder-grid">
      <div className="catalog-pane"><input className="search-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="名前・ID・タイプ検索" /><div className="catalog-list">{visible.map((card) => <article key={card.cardId} className="catalog-card"><div><small>#{card.cardId} · {card.expansion}</small><strong>{card.name}</strong><span>{card.stageOrType} · {card.hp ? `HP ${card.hp}` : card.pokemonType}</span></div><button type="button" onClick={() => change(card, 1)} disabled={total >= 60 || (!card.basicEnergy && (deck.get(card.cardId) || 0) >= 4)}>＋</button></article>)}</div></div>
      <div className="deck-pane"><div className="deck-pane-head"><strong>Current Deck</strong><button type="button" onClick={exportDeck} disabled={total === 0}>Export deck.csv</button></div><div className="deck-list">{deckRows.length ? deckRows.map(([id, count]) => { const card = byId.get(id); return <article key={id}><div><small>#{id}</small><strong>{card?.name || `Card ${id}`}</strong><span>{card?.stageOrType || "Bundle import"}</span></div><div className="qty"><button type="button" onClick={() => card ? change(card, -1) : decrementUnknown(id, count)}>−</button><b>{count}</b><button type="button" onClick={() => card && change(card, 1)} disabled={!card || total >= 60 || (!card.basicEnergy && count >= 4)}>＋</button></div></article>; }) : <p className="muted">カードの＋を押して追加。</p>}</div></div>
    </div>}
  </section>;
}
