import type { CatalogCard } from "./cardCatalog";

export type DeckIssue = { code: string; message: string };
export type DeckStats = {
  total: number;
  pokemon: number;
  trainer: number;
  energy: number;
  aceSpec: number;
  basicPokemon: number;
  unique: number;
  issues: DeckIssue[];
};

export function isBasicEnergy(card: CatalogCard): boolean {
  return card.kind === "Energy" && card.stage.toLowerCase().includes("basic energy");
}

export function isBasicPokemon(card: CatalogCard): boolean {
  return card.kind === "Pokemon" && card.stage.toLowerCase().startsWith("basic");
}

export function aggregateDeck(ids: number[]): Map<number, number> {
  const counts = new Map<number, number>();
  ids.forEach((id) => counts.set(id, (counts.get(id) ?? 0) + 1));
  return counts;
}

export function validateDeck(ids: number[], cardsById: Map<number, CatalogCard>): DeckStats {
  const issues: DeckIssue[] = [];
  const countsByName = new Map<string, number>();
  let pokemon = 0;
  let trainer = 0;
  let energy = 0;
  let aceSpec = 0;
  let basicPokemon = 0;
  let unknown = 0;

  ids.forEach((id) => {
    const card = cardsById.get(id);
    if (!card) { unknown += 1; return; }
    if (card.kind === "Pokemon") pokemon += 1;
    if (card.kind === "Trainer") trainer += 1;
    if (card.kind === "Energy") energy += 1;
    if (card.rule.toUpperCase() === "ACE SPEC") aceSpec += 1;
    if (isBasicPokemon(card)) basicPokemon += 1;
    if (!isBasicEnergy(card)) countsByName.set(card.name, (countsByName.get(card.name) ?? 0) + 1);
  });

  if (ids.length !== 60) issues.push({ code: "DECK_SIZE", message: `60枚必要（現在${ids.length}枚）` });
  if (unknown) issues.push({ code: "UNKNOWN_CARD", message: `カードDBにないIDが${unknown}枚` });
  if (basicPokemon === 0) issues.push({ code: "NO_BASIC", message: "たねポケモンが1枚以上必要" });
  if (aceSpec > 1) issues.push({ code: "ACE_SPEC", message: `ACE SPECは合計1枚まで（現在${aceSpec}枚）` });
  for (const [name, count] of countsByName) {
    if (count > 4) issues.push({ code: "COPY_LIMIT", message: `${name}は同名4枚まで（現在${count}枚）` });
  }

  return { total: ids.length, pokemon, trainer, energy, aceSpec, basicPokemon, unique: aggregateDeck(ids).size, issues };
}

export function parseDeckCsv(text: string): number[] {
  const values: number[] = [];
  const tokens = text.replace(/^\uFEFF/, "").split(/[\s,;]+/).filter(Boolean);
  for (const token of tokens) {
    const value = Number(token);
    if (Number.isInteger(value) && value > 0) values.push(value);
    else if (values.length > 0) throw new Error(`不正なカードID: ${token}`);
  }
  if (!values.length) throw new Error("deck.csvにカードIDがありません");
  if (values.length > 60) throw new Error(`60枚を超えています（${values.length}枚）`);
  return values;
}

export function deckCsv(ids: number[]): string {
  return `${ids.join("\n")}\n`;
}
