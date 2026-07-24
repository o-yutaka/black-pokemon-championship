import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { APPLY_PLAYER_DECK_EVENT, BUNDLE_DECK_EVENT, PLAYER_BUNDLE_SELECTED_EVENT, PLAYER_BUNDLE_UPDATED_EVENT, deckCsv, parseDeckCsv, type PlayerBundleDetail } from "./deck-easy";
import { catalogTermJa } from "./locale";
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

type SelectedPlayer = {
  bundleId: string;
  filename: string;
  canApplyDirectly: boolean;
};

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
  return [card.id, card.name, card.expansion, card.number, card.kind, card.stage, card.previous, card.type, card.rule, ...card.moves.flatMap((move) => [move.name, move.cost, move.damage, move.text])].join(" ").toLowerCase();
}

function countsFromIds(ids: number[]): Map<number, number> {
  const next = new Map<number, number>();
  ids.forEach((id) => next.set(id, (next.get(id) ?? 0) + 1));
  return next;
}

function hpText(value: string): string {
  return value && value.toLowerCase() !== "n/a" ? `HP ${value.replace(/\.0$/, "")}` : "";
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
  const [selectedPlayer, setSelectedPlayer] = useState<SelectedPlayer | null>(null);
  const [applyMessage, setApplyMessage] = useState<string | null>(null);
  const csvRef = useRef<HTMLInputElement>(null);

  const loadCatalog = useCallback(async () => {
    const value = bridgeUrl.trim();
    if (!value) { setCatalogError("接続先URLを入力してください"); return; }
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      const base = new URL(value);
      localStorage.setItem("black.bridgeUrl", base.toString());
      const response = await fetch(new URL("/api/cards", base), { cache: "no-store" });
      const payload = await response.json().catch(() => ({})) as { cards?: CatalogCard[]; detail?: string };
      if (!response.ok) throw new Error(payload.detail || `カードDBの通信に失敗しました（HTTP ${response.status}）`);
      if (!Array.isArray(payload.cards)) throw new Error("カードDBの形式が正しくありません");
      setCatalog(payload.cards);
    } catch (error) {
      setCatalogError(error instanceof Error ? error.message : "カードDBを読み込めませんでした");
    } finally {
      setCatalogLoading(false);
    }
  }, [bridgeUrl]);

  const replaceDeck = useCallback((ids: number[]) => {
    setDeck(countsFromIds(ids));
    setApplyMessage(null);
  }, []);

  useEffect(() => { if (bridgeUrl) void loadCatalog(); }, []);
  useEffect(() => { if (importedDeck) replaceDeck(importedDeck); }, [importedDeck, replaceDeck]);

  useEffect(() => {
    const handleDeck = (event: Event) => {
      const detail = (event as CustomEvent<unknown>).detail;
      if (Array.isArray(detail) && detail.every((value) => Number.isInteger(value))) replaceDeck(detail as number[]);
    };
    const handlePlayer = (event: Event) => {
      const detail = (event as CustomEvent<PlayerBundleDetail>).detail;
      if (!detail?.bundle) return;
      setSelectedPlayer({ bundleId: detail.bundle.id, filename: detail.bundle.filename, canApplyDirectly: detail.canApplyDirectly });
      replaceDeck(detail.deck);
      setApplyMessage(detail.canApplyDirectly ? "自分の対戦AIのデッキを読み込みました" : "デッキを読み込みました。直接反映する場合はフォルダーから選び直してください");
    };
    const handleUpdated = (event: Event) => {
      const detail = (event as CustomEvent<PlayerBundleDetail>).detail;
      if (!detail?.bundle) return;
      setSelectedPlayer({ bundleId: detail.bundle.id, filename: detail.bundle.filename, canApplyDirectly: detail.canApplyDirectly });
      replaceDeck(detail.deck);
      setApplyMessage("自分の対戦AIへ新しい60枚を反映しました");
    };
    const reloadCatalog = () => void loadCatalog();
    window.addEventListener(BUNDLE_DECK_EVENT, handleDeck);
    window.addEventListener(PLAYER_BUNDLE_SELECTED_EVENT, handlePlayer);
    window.addEventListener(PLAYER_BUNDLE_UPDATED_EVENT, handleUpdated);
    window.addEventListener("black:card-catalog-updated", reloadCatalog);
    return () => {
      window.removeEventListener(BUNDLE_DECK_EVENT, handleDeck);
      window.removeEventListener(PLAYER_BUNDLE_SELECTED_EVENT, handlePlayer);
      window.removeEventListener(PLAYER_BUNDLE_UPDATED_EVENT, handleUpdated);
      window.removeEventListener("black:card-catalog-updated", reloadCatalog);
    };
  }, [loadCatalog, replaceDeck]);

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
      if (!card) { unknownCount += count; continue; }
      nameCounts.set(card.name, (nameCounts.get(card.name) ?? 0) + count);
      if (card.ace) aceCount += count;
      if (card.basicPokemon) basicPokemonCount += count;
    }
    if (total !== 60) errors.push(`デッキは60枚必要です（現在${total}枚）`);
    if (unknownCount) errors.push(`カードDBにないIDが${unknownCount}枚あります`);
    for (const [name, count] of nameCounts.entries()) {
      const sample = catalog.find((card) => card.name === name);
      if (!sample?.basicEnergy && count > 4) errors.push(`${name}が同名4枚を超えています（${count}枚）`);
    }
    if (aceCount > 1) errors.push(`ACE SPECは合計1枚までです（現在${aceCount}枚）`);
    if (basicPokemonCount === 0) errors.push("たねポケモンを1枚以上入れてください");
    if (total > 0 && total < 60) warnings.push(`あと${60 - total}枚追加してください`);
    if (total > 60) warnings.push(`${total - 60}枚減らしてください`);
    return { ok: errors.length === 0, errors, warnings, total };
  }, [catalog, catalogById, deck, total]);

  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return catalog.filter((card) => (!kind || (card.kind || card.stage) === kind) && (!normalized || searchIndex.get(card.id)?.includes(normalized))).slice(0, 120);
  }, [catalog, kind, query, searchIndex]);

  const deckRows = useMemo(() => [...deck.entries()].filter(([, count]) => count > 0).map(([id, count]) => ({ id, count, card: catalogById.get(id) })).sort((a, b) => (a.card?.name ?? "").localeCompare(b.card?.name ?? "") || a.id - b.id), [catalogById, deck]);
  const deckIds = useMemo(() => deckRows.flatMap((row) => Array.from({ length: row.count }, () => row.id)), [deckRows]);

  const setExactCount = useCallback((id: number, count: number) => {
    setDeck((current) => {
      const next = new Map(current);
      if (count <= 0) next.delete(id); else next.set(id, count);
      return next;
    });
    setApplyMessage(null);
  }, []);

  const changeCount = useCallback((id: number, delta: number) => {
    const current = deck.get(id) ?? 0;
    setExactCount(id, Math.max(0, current + delta));
  }, [deck, setExactCount]);

  const exportCsv = () => {
    if (!validation.ok) return;
    downloadText("deck.csv", deckCsv(deckIds), "text/csv;charset=utf-8");
  };

  const importCsv = async (file?: File) => {
    if (!file) return;
    try {
      replaceDeck(parseDeckCsv(await file.text()));
      setApplyMessage("デッキCSVを読み込みました");
    } catch (error) {
      setApplyMessage(error instanceof Error ? error.message : "デッキCSVを読み込めませんでした");
    }
  };

  const applyToPlayer = () => {
    if (!validation.ok || !selectedPlayer?.canApplyDirectly) return;
    setApplyMessage("自分の対戦AIへ反映しています…");
    window.dispatchEvent(new CustomEvent(APPLY_PLAYER_DECK_EVENT, { detail: { deck: deckIds } }));
  };

  const selectedCard = selectedId === null ? null : catalogById.get(selectedId) ?? null;
  const canApply = Boolean(validation.ok && selectedPlayer?.canApplyDirectly);

  return (
    <section className="deck-builder" aria-label="かんたんデッキ作成">
      <div className="deck-builder-head">
        <div><span className="eyebrow">かんたんデッキ作成</span><h2>カードを検索して枚数を押すだけ</h2><p>自分の対戦AIを選ぶと現在の60枚を自動読込。変更後はそのまま反映できる。</p></div>
        <div className={`deck-total ${validation.ok ? "valid" : "invalid"}`}><strong>{total}</strong><span>/ 60枚</span></div>
      </div>

      <div className="deck-easy-guide">
        <div className={selectedPlayer ? "done" : ""}><b>1</b><span>上で自分の対戦AIフォルダーを選ぶ</span></div>
        <div><b>2</b><span>カードを検索して0〜4枚を押す</span></div>
        <div className={validation.ok ? "done" : ""}><b>3</b><span>60枚とルール違反なしを確認</span></div>
        <div className={canApply ? "ready" : ""}><b>4</b><span>自分の対戦AIへ反映</span></div>
      </div>

      <div className="deck-player-status">
        <div><strong>{selectedPlayer ? `選択中: ${selectedPlayer.filename}` : "自分の対戦AIはまだ選ばれていません"}</strong><span>{selectedPlayer?.canApplyDirectly ? "画面からデッキを直接変更できます" : "上の『自分の対戦AI』でフォルダーを選ぶと直接変更できます"}</span></div>
        <button className="primary" type="button" onClick={applyToPlayer} disabled={!canApply}>この60枚を自分の対戦AIへ反映</button>
      </div>
      {applyMessage && <div className={`deck-alert ${applyMessage.includes("ません") || applyMessage.includes("必要") ? "error" : ""}`}>{applyMessage}</div>}

      <details className="deck-advanced"><summary>接続先・CSVの予備操作</summary><div className="deck-bridge-row"><label>カードDBの接続先<input value={bridgeUrl} onChange={(event) => setBridgeUrl(event.target.value)} placeholder="http://192.168.x.x:8000" spellCheck={false} autoCapitalize="none" autoCorrect="off" inputMode="url" /></label><button type="button" onClick={() => void loadCatalog()} disabled={catalogLoading}>{catalogLoading ? "読み込み中…" : "カードDBを再読込"}</button></div><div className="deck-file-actions"><button type="button" onClick={() => csvRef.current?.click()}>デッキCSVを読み込む</button><button type="button" onClick={exportCsv} disabled={!validation.ok}>deck.csvを保存</button></div></details>
      <input ref={csvRef} className="file-input" type="file" accept=".csv,text/csv" onChange={(event) => { void importCsv(event.target.files?.[0]); event.currentTarget.value = ""; }} />
      {catalogError && <div className="deck-alert error">{catalogError}</div>}
      {!catalog.length && !catalogError && <div className="deck-alert">カードDBを読み込んでいます…</div>}

      <div className="deck-builder-grid">
        <div className="catalog-pane">
          <div className="catalog-tools"><label>カード検索<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="名前・ID・ワザ・効果" inputMode="search" /></label><label>カードの種類<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="">すべて表示</option>{kinds.map((value) => <option key={value} value={value}>{catalogTermJa(value)}</option>)}</select></label></div>
          <div className="catalog-count">{results.length}件表示 / 全{catalog.length}カード</div>
          <div className="catalog-results">
            {results.map((card) => {
              const count = deck.get(card.id) ?? 0;
              return <article className="catalog-card easy-card" key={card.id} data-card-id={card.id}>
                <button className="catalog-card-main" type="button" onClick={() => setSelectedId(card.id)}><span className="catalog-id">#{card.id} · {card.expansion} {card.number}</span><strong>{card.name}</strong><span className="catalog-meta">{[catalogTermJa(card.stage || card.kind), catalogTermJa(card.type), hpText(card.hp)].filter(Boolean).join(" · ")}</span><span className="catalog-move">{card.moves[0]?.name || card.rule || "効果なし"}</span></button>
                <div className="quick-count" aria-label={`${card.name}の枚数`}><button type="button" className={count === 0 ? "active" : ""} onClick={() => setExactCount(card.id, 0)}>0</button>{[1, 2, 3, 4].map((value) => <button type="button" key={value} className={count === value ? "active" : ""} onClick={() => setExactCount(card.id, value)}>{value}</button>)}{card.basicEnergy && <button type="button" onClick={() => changeCount(card.id, 1)}>＋</button>}</div>
              </article>;
            })}
            {catalog.length > 0 && results.length === 0 && <div className="deck-empty">条件に合うカードがありません</div>}
          </div>
        </div>

        <aside className="deck-pane">
          <div className="deck-pane-head"><div><h3>現在のデッキ</h3><span>{deckRows.length}種類 · 合計{total}枚</span></div><button type="button" onClick={() => { setDeck(new Map()); setApplyMessage(null); }} disabled={total === 0}>全部外す</button></div>
          <div className="deck-validation">{validation.ok ? <div className="deck-valid">公式ルール上、使用可能な60枚です</div> : validation.errors.map((message) => <div className="deck-invalid" key={message}>{message}</div>)}{validation.warnings.map((message) => <div className="deck-warning" key={message}>{message}</div>)}</div>
          <div className="deck-list">{deckRows.map(({ id, count, card }) => <div className="deck-row easy-row" key={id}><button className="deck-card-name" type="button" onClick={() => setSelectedId(id)}><span>#{id}</span><strong>{card?.name ?? `不明なカード #${id}`}</strong></button><div className="deck-stepper"><button type="button" onClick={() => changeCount(id, -1)} aria-label="1枚減らす">−</button><b>{count}枚</b><button type="button" onClick={() => changeCount(id, 1)} aria-label="1枚増やす">＋</button></div></div>)}{deckRows.length === 0 && <div className="deck-empty">左のカードで枚数を押すと、ここに追加されます</div>}</div>
          <button className="deck-export primary" type="button" onClick={applyToPlayer} disabled={!canApply}>自分の対戦AIへ反映</button>
        </aside>
      </div>

      <div className={`mobile-deck-bar ${validation.ok ? "valid" : "invalid"}`}><div><strong>{total}/60枚</strong><span>{validation.ok ? selectedPlayer?.canApplyDirectly ? "反映できます" : "フォルダーから対戦AIを選んでください" : validation.errors[0] ?? "編集中"}</span></div><button type="button" className="primary" onClick={applyToPlayer} disabled={!canApply}>反映</button></div>

      {selectedCard && <div className="deck-modal-backdrop" role="presentation" onMouseDown={() => setSelectedId(null)}><section className="deck-modal" role="dialog" aria-modal="true" aria-label={selectedCard.name} onMouseDown={(event) => event.stopPropagation()}><button className="deck-modal-close" type="button" onClick={() => setSelectedId(null)}>閉じる</button><span className="catalog-id">#{selectedCard.id} · {selectedCard.expansion} {selectedCard.number}</span><h3>{selectedCard.name}</h3><p>{[catalogTermJa(selectedCard.stage || selectedCard.kind), catalogTermJa(selectedCard.type), hpText(selectedCard.hp), selectedCard.previous && `進化元 ${selectedCard.previous}`].filter(Boolean).join(" · ")}</p>{selectedCard.rule && <div className="deck-rule">{selectedCard.rule}</div>}<div className="move-list">{selectedCard.moves.map((move, index) => <article key={`${move.name}-${index}`}><div><strong>{move.name || "特性"}</strong><span>{move.cost} {move.damage}</span></div>{move.text && <p>{move.text}</p>}</article>)}</div><div className="modal-count"><span>このカードの枚数</span><div className="quick-count">{[0, 1, 2, 3, 4].map((value) => <button type="button" key={value} className={(deck.get(selectedCard.id) ?? 0) === value ? "active" : ""} onClick={() => setExactCount(selectedCard.id, value)}>{value}</button>)}</div></div></section></div>}
    </section>
  );
}
