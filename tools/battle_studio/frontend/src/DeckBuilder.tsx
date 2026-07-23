import { useEffect, useMemo, useState } from "react";
import "./deck-builder.css";

export type CatalogMove = { name: string; cost: string; damage: string; text: string };
export type CatalogCard = {
  id: number;
  name: string;
  expansion: string;
  number: string;
  kind: string;
  stage: string;
  previous: string;
  hp: string;
  type: string;
  rule: string;
  moves: CatalogMove[];
  basicEnergy: boolean;
  basicPokemon: boolean;
  ace: boolean;
};

type DeckValidation = { ok: boolean; errors: string[]; warnings: string[]; total: number };

function downloadText(filename: string, text: string, type: string): void {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function cardSearchText(card: CatalogCard): string {
  return [
    card.id,
    card.name,
    card.expansion,
    card.number,
    card.kind,
    card.stage,
    card.previous,
    card.type,
    card.rule,
    ...card.moves.flatMap((move) => [move.name, move.cost, move.damage, move.text]),
  ].join(" ").toLowerCase();
}

function countsFromIds(ids: number[]): Map<number, number> {
  const next = new Map<number, number>();
  ids.forEach((id) => next.set(id, (next.get(id) ?? 0) + 1));
  return next;
}

export function DeckBuilder({ importedDeck }: { importedDeck: number[] | null }) {
  const defaultBridge = localStorage.getItem("black.bridgeUrl") || (!window.location.hostname.endsWith("github.io") ? window.location.origin : "");
  const [bridgeUrl, setBridgeUrl] = useState(defaultBridge);
  const [catalog, setCatalog] = useState<CatalogCard[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [deck, setDeck] = useState<Map<number, number>>(() => new Map());
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const loadCatalog = async () => {
    const value = bridgeUrl.trim();
    if (!value) {
      setCatalogError("Bridge URLを入力してください");
      return;
    }
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      const base = new URL(value);
      localStorage.setItem("black.bridgeUrl", base.toString());
      const response = await fetch(new URL("/api/cards", base), { cache: "no-store" });
      const payload = await response.json().catch(() => ({})) as { cards?: CatalogCard[]; detail?: string };
      if (!response.ok) throw new Error(payload.detail || `Card catalog HTTP ${response.status}`);
      if (!Array.isArray(payload.cards)) throw new Error("Bridge returned an invalid card catalog");
      setCatalog(payload.cards);
    } catch (error) {
      setCatalogError(error instanceof Error ? error.message : "Card catalog load failed");
    } finally {
      setCatalogLoading(false);
    }
  };

  useEffect(() => {
    if (bridgeUrl) void loadCatalog();
  }, []);

  useEffect(() => {
    if (importedDeck) setDeck(countsFromIds(importedDeck));
  }, [importedDeck]);

  useEffect(() => {
    const handleBundleDeck = (event: Event) => {
      const detail = (event as CustomEvent<unknown>).detail;
      if (Array.isArray(detail) && detail.every((value) => Number.isInteger(value))) {
        setDeck(countsFromIds(detail as number[]));
      }
    };
    window.addEventListener("black:bundle-deck", handleBundleDeck);
    return () => window.removeEventListener("black:bundle-deck", handleBundleDeck);
  }, []);

  const catalogById = useMemo(() => new Map(catalog.map((card) => [card.id, card])), [catalog]);
  const kinds = useMemo(() => [...new Set(catalog.map((card) => card.kind || card.stage).filter(Boolean))].sort(), [catalog]);
  const searchIndex = useMemo(() => new Map(catalog.map((card) => [card.id, cardSearchText(card)])), [catalog]);
  const total = useMemo(() => [...deck.values()].reduce((sum, count) => sum + count, 0), [deck]);

  const validation = useMemo<DeckValidation>(() => {
    const errors: string[] = [];
    const warnings: string[] = [];
    const nameCounts = new Map<string, number>();
    let aceCount = 0;
    let basicPokemonCount = 0;
    let unknownCount = 0;
    for (const [id, count] of deck.entries()) {
      const card = catalogById.get(id);
      if (!card) {
        unknownCount += count;
        continue;
      }
      nameCounts.set(card.name, (nameCounts.get(card.name) ?? 0) + count);
      if (card.ace) aceCount += count;
      if (card.basicPokemon) basicPokemonCount += count;
    }
    if (total !== 60) errors.push(`デッキは60枚必要（現在${total}枚）`);
    if (unknownCount) errors.push(`カードDBにないIDが${unknownCount}枚ある`);
    for (const [name, count] of nameCounts.entries()) {
      const sample = catalog.find((card) => card.name === name);
      if (!sample?.basicEnergy && count > 4) errors.push(`${name} が同名4枚を超過（${count}枚）`);
    }
    if (aceCount > 1) errors.push(`ACE SPECは合計1枚まで（現在${aceCount}枚）`);
    if (basicPokemonCount === 0) errors.push("たねポケモンが1枚以上必要");
    if (total > 0 && total < 60) warnings.push(`あと${60 - total}枚`);
    if (total > 60) warnings.push(`${total - 60}枚減らす必要あり`);
    return { ok: errors.length === 0, errors, warnings, total };
  }, [catalog, catalogById, deck, total]);

  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return catalog
      .filter((card) => (!kind || (card.kind || card.stage) === kind) && (!normalized || searchIndex.get(card.id)?.includes(normalized)))
      .slice(0, 100);
  }, [catalog, kind, query, searchIndex]);

  const deckRows = useMemo(() => [...deck.entries()]
    .filter(([, count]) => count > 0)
    .map(([id, count]) => ({ id, count, card: catalogById.get(id) }))
    .sort((a, b) => (a.card?.name ?? `#${a.id}`).localeCompare(b.card?.name ?? `#${b.id}`, undefined, { numeric: true })), [catalogById, deck]);

  const changeCount = (id: number, delta: number) => {
    setDeck((current) => {
      const next = new Map<number, number>(current);
      const value = Math.max(0, (next.get(id) ?? 0) + delta);
      if (value === 0) next.delete(id);
      else next.set(id, value);
      return next;
    });
  };

  const exportCsv = () => {
    if (!validation.ok) return;
    const ids = deckRows.flatMap((row) => Array.from({ length: row.count }, () => row.id));
    downloadText("deck.csv", `${ids.join("\n")}\n`, "text/csv;charset=utf-8");
  };

  const selectedCard = selectedId === null ? null : catalogById.get(selectedId) ?? null;

  return (
    <section className="deck-builder" aria-label="Card search deck builder">
      <div className="deck-builder-head">
        <div>
          <span className="eyebrow">OFFICIAL CARD DATABASE</span>
          <h2>カード検索式デッキビルダー</h2>
          <p>カードを検索して追加し、Kaggle用の60枚 <code>deck.csv</code> を作成する。</p>
        </div>
        <div className={`deck-total ${validation.ok ? "valid" : "invalid"}`}><strong>{total}</strong><span>/ 60</span></div>
      </div>

      <div className="deck-bridge-row">
        <label>Card DB Bridge<input value={bridgeUrl} onChange={(event) => setBridgeUrl(event.target.value)} placeholder="http://192.168.x.x:8000" spellCheck={false} autoCapitalize="none" autoCorrect="off" inputMode="url" /></label>
        <button type="button" onClick={() => void loadCatalog()} disabled={catalogLoading}>{catalogLoading ? "読込中…" : "カードDB読込"}</button>
      </div>
      {catalogError && <div className="deck-alert error">{catalogError}</div>}
      {!catalog.length && !catalogError && <div className="deck-alert">カードDB読込中…</div>}

      <div className="deck-builder-grid">
        <div className="catalog-pane">
          <div className="catalog-tools">
            <label>カード検索<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="名前・ID・ワザ・効果" inputMode="search" /></label>
            <label>分類<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="">すべて</option>{kinds.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          </div>
          <div className="catalog-count">{results.length}件表示 / {catalog.length}カード</div>
          <div className="catalog-results">
            {results.map((card) => {
              const count = deck.get(card.id) ?? 0;
              return <article className="catalog-card" key={card.id}>
                <button className="catalog-card-main" type="button" onClick={() => setSelectedId(card.id)}>
                  <span className="catalog-id">#{card.id} · {card.expansion} {card.number}</span>
                  <strong>{card.name}</strong>
                  <span className="catalog-meta">{[card.stage || card.kind, card.type, card.hp && `HP ${Number(card.hp)}`].filter(Boolean).join(" · ")}</span>
                  <span className="catalog-move">{card.moves[0]?.name || card.rule || "効果なし"}</span>
                </button>
                <div className="catalog-add">
                  {count > 0 && <span>{count}枚</span>}
                  <button type="button" onClick={() => changeCount(card.id, 1)} aria-label={`${card.name}を1枚追加`}>＋</button>
                </div>
              </article>;
            })}
            {catalog.length > 0 && results.length === 0 && <div className="deck-empty">該当カードなし</div>}
          </div>
        </div>

        <aside className="deck-pane">
          <div className="deck-pane-head">
            <div><h3>MY DECK</h3><span>{deckRows.length}種類</span></div>
            <button type="button" onClick={() => setDeck(new Map())} disabled={total === 0}>全削除</button>
          </div>
          <div className="deck-validation">
            {validation.ok ? <div className="deck-valid">提出可能な60枚デッキ</div> : validation.errors.map((message) => <div className="deck-invalid" key={message}>{message}</div>)}
            {validation.warnings.map((message) => <div className="deck-warning" key={message}>{message}</div>)}
          </div>
          <div className="deck-list">
            {deckRows.map(({ id, count, card }) => <div className="deck-row" key={id}>
              <button className="deck-card-name" type="button" onClick={() => setSelectedId(id)}><span>#{id}</span><strong>{card?.name ?? `Unknown #${id}`}</strong></button>
              <div className="deck-stepper"><button type="button" onClick={() => changeCount(id, -1)} aria-label="1枚減らす">−</button><b>{count}</b><button type="button" onClick={() => changeCount(id, 1)} aria-label="1枚増やす">＋</button></div>
            </div>)}
            {deckRows.length === 0 && <div className="deck-empty">検索結果からカードを追加</div>}
          </div>
          <button className="deck-export primary" type="button" onClick={exportCsv} disabled={!validation.ok}>deck.csvを書き出す</button>
        </aside>
      </div>

      <div className={`mobile-deck-bar ${validation.ok ? "valid" : "invalid"}`}>
        <div><strong>{total}/60</strong><span>{validation.ok ? "提出可能" : validation.errors[0] ?? "編集中"}</span></div>
        <button type="button" className="primary" onClick={exportCsv} disabled={!validation.ok}>CSV</button>
      </div>

      {selectedCard && <div className="deck-modal-backdrop" role="presentation" onMouseDown={() => setSelectedId(null)}>
        <section className="deck-modal" role="dialog" aria-modal="true" aria-label={selectedCard.name} onMouseDown={(event) => event.stopPropagation()}>
          <button className="deck-modal-close" type="button" onClick={() => setSelectedId(null)}>閉じる</button>
          <span className="catalog-id">#{selectedCard.id} · {selectedCard.expansion} {selectedCard.number}</span>
          <h3>{selectedCard.name}</h3>
          <p>{[selectedCard.stage || selectedCard.kind, selectedCard.type, selectedCard.hp && `HP ${Number(selectedCard.hp)}`, selectedCard.previous && `進化元 ${selectedCard.previous}`].filter(Boolean).join(" · ")}</p>
          {selectedCard.rule && <div className="deck-rule">{selectedCard.rule}</div>}
          <div className="move-list">{selectedCard.moves.map((move, index) => <article key={`${move.name}-${index}`}><div><strong>{move.name || "Ability"}</strong><span>{move.cost} {move.damage}</span></div>{move.text && <p>{move.text}</p>}</article>)}</div>
          <button className="primary modal-add" type="button" onClick={() => changeCount(selectedCard.id, 1)}>デッキに追加</button>
        </section>
      </div>}
    </section>
  );
}
