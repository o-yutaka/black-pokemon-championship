import {
  EMBEDDED_CARD_CATALOG_COUNT,
  EMBEDDED_CARD_CATALOG_GZIP_BASE64,
  EMBEDDED_CARD_CATALOG_SOURCES,
} from "./catalogData";

export type CatalogMove = {
  kind: "ability" | "tera" | "attack";
  attackId: number | null;
  name: string;
  cost: string;
  damage: string;
  text: string;
  engineName: string;
};

export type CatalogCard = {
  id: number;
  name: string;
  expansion: string;
  collectionNo: string;
  kind: "Pokemon" | "Trainer" | "Energy";
  stage: string;
  rule: string;
  category: string;
  previousStage: string;
  hp: number | null;
  type: string;
  weakness: string;
  resistance: string;
  retreat: number | null;
  moves: CatalogMove[];
};

type RawMove = { k: CatalogMove["kind"]; i?: number; n: string; c?: string; d?: string; t?: string; en?: string };
type RawCard = { i: number; n: string; e: string; o: string; k: CatalogCard["kind"]; s: string; r: string; g: string; p: string; h: number | null; y: string; w: string; x: string; q: number | null; m: RawMove[] };

let cache: Promise<{ cards: CatalogCard[]; sources: Record<string, string> }> | null = null;

function decodeCard(raw: RawCard): CatalogCard {
  return {
    id: raw.i,
    name: raw.n,
    expansion: raw.e,
    collectionNo: raw.o,
    kind: raw.k,
    stage: raw.s,
    rule: raw.r,
    category: raw.g,
    previousStage: raw.p,
    hp: raw.h,
    type: raw.y,
    weakness: raw.w,
    resistance: raw.x,
    retreat: raw.q,
    moves: raw.m.map((move) => ({
      kind: move.k,
      attackId: move.i ?? null,
      name: move.n,
      cost: move.c ?? "",
      damage: move.d ?? "",
      text: move.t ?? "",
      engineName: move.en ?? "",
    })),
  };
}

async function decodeEmbeddedJson(): Promise<RawCard[]> {
  if (typeof DecompressionStream === "undefined") {
    throw new Error("このブラウザは内蔵カードDBの展開に対応していません");
  }
  const binary = atob(EMBEDDED_CARD_CATALOG_GZIP_BASE64);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  const text = await new Response(stream).text();
  return JSON.parse(text) as RawCard[];
}

export function loadCardCatalog(): Promise<{ cards: CatalogCard[]; sources: Record<string, string> }> {
  cache ??= decodeEmbeddedJson().then((rawCards) => {
    const cards = rawCards.map(decodeCard).sort((a, b) => a.id - b.id);
    if (cards.length !== EMBEDDED_CARD_CATALOG_COUNT) {
      throw new Error(`Card catalog count mismatch: ${cards.length}/${EMBEDDED_CARD_CATALOG_COUNT}`);
    }
    return { cards, sources: EMBEDDED_CARD_CATALOG_SOURCES };
  });
  return cache;
}
