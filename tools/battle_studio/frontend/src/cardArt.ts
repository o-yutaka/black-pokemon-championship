import { useEffect, useMemo, useState } from "react";

export type CardArtCatalog = Map<number, string>;
export type PublicCardCatalogEntry = { id: number; name: string; number: string; expansion: string; sourceLink: string };
type UnknownRecord = Record<string, unknown>;
type CatalogCard = PublicCardCatalogEntry;

const CACHE_KEY = "black.real-card-art.v1";
const API_ROOT = "https://api.pokemontcg.io/v2/cards";

function asRecord(value: unknown): UnknownRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as UnknownRecord : null;
}

function pickNumber(record: UnknownRecord): number | null {
  for (const key of ["cardId", "card_id", "id", "Card ID", "ID"]) {
    const value = record[key];
    const numberValue = typeof value === "number" ? value : Number(value);
    if (Number.isInteger(numberValue) && numberValue >= 0) return numberValue;
  }
  return null;
}

function pickUrl(record: UnknownRecord): string | null {
  for (const key of ["imageUrl", "image_url", "image", "artUrl", "art_url", "cardImage", "card_image"]) {
    const value = record[key];
    if (typeof value === "string" && /^https?:\/\//i.test(value)) return value;
  }
  return null;
}

function collectRows(payload: unknown): unknown[] {
  if (Array.isArray(payload)) return payload;
  const record = asRecord(payload);
  if (!record) return [];
  for (const key of ["cards", "items", "results", "data"]) {
    if (Array.isArray(record[key])) return record[key] as unknown[];
  }
  return [];
}

function text(record: UnknownRecord, ...keys: string[]): string {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function readCache(): Record<string, string> {
  try {
    const value = JSON.parse(localStorage.getItem(CACHE_KEY) ?? "{}");
    return value && typeof value === "object" ? value as Record<string, string> : {};
  } catch { return {}; }
}

function normalizeNumber(value: string): string {
  return value.replace(/[^0-9A-Za-z]/g, "").replace(/^0+/, "") || "0";
}

function directImage(link: string): string | null {
  const match = link.match(/https?:\/\/images\.pokemontcg\.io\/[^\s]+/i);
  return match?.[0] ?? null;
}

async function resolveFromApi(card: CatalogCard, signal: AbortSignal): Promise<string | null> {
  const direct = directImage(card.sourceLink);
  if (direct) return direct;
  const linkedId = card.sourceLink.match(/(?:api\.pokemontcg\.io\/v2\/cards\/|pokemontcg\.io\/card\/)([A-Za-z0-9.-]+)/i)?.[1];
  if (linkedId) {
    const response = await fetch(`${API_ROOT}/${encodeURIComponent(linkedId)}?select=id,images`, { signal, cache: "force-cache" });
    if (!response.ok) return null;
    const payload = await response.json() as { data?: { images?: { small?: string; large?: string } } };
    return payload.data?.images?.small ?? payload.data?.images?.large ?? null;
  }
  if (!card.name || !card.number) return null;
  const cleanName = card.name.replace(/"/g, "");
  const cleanNumber = card.number.replace(/"/g, "");
  const query = `name:"${cleanName}" number:"${cleanNumber}"`;
  const params = new URLSearchParams({ q: query, select: "id,name,number,set,images", pageSize: "20" });
  const response = await fetch(`${API_ROOT}?${params}`, { signal, cache: "force-cache" });
  if (!response.ok) return null;
  const payload = await response.json() as { data?: Array<{ name?: string; number?: string; set?: Record<string, string>; images?: { small?: string; large?: string } }> };
  const wantedNumber = normalizeNumber(card.number);
  const wantedExpansion = card.expansion.toLowerCase();
  const ranked = (payload.data ?? []).map((candidate) => {
    let score = 0;
    if ((candidate.name ?? "").toLowerCase() === card.name.toLowerCase()) score += 100;
    if (normalizeNumber(candidate.number ?? "") === wantedNumber) score += 50;
    const setText = Object.values(candidate.set ?? {}).join(" ").toLowerCase();
    if (wantedExpansion && setText.includes(wantedExpansion)) score += 25;
    return { score, url: candidate.images?.small ?? candidate.images?.large ?? null };
  }).filter((candidate) => candidate.url).sort((a, b) => b.score - a.score);
  return ranked[0]?.score >= 150 ? ranked[0].url : null;
}

async function resolveCards(rows: CatalogCard[], cache: Record<string, string>, signal: AbortSignal): Promise<void> {
  for (const card of rows) {
    const direct = directImage(card.sourceLink);
    if (direct) cache[String(card.id)] = direct;
  }
  for (const card of rows) {
    if (cache[String(card.id)]) continue;
    const url = await resolveFromApi(card, signal).catch(() => null);
    if (url) cache[String(card.id)] = url;
  }
}

export function useCardArtCatalog(requestedIds: number[], publicCards: PublicCardCatalogEntry[] = []): CardArtCatalog {
  const [entries, setEntries] = useState<Array<[number, string]>>(() => Object.entries(readCache()).map(([id, url]) => [Number(id), url]));
  const idKey = [...new Set(requestedIds)].sort((a, b) => a - b).join(",");
  const publicKey = publicCards.map((card) => `${card.id}:${card.name}:${card.number}:${card.expansion}:${card.sourceLink}`).join("|");
  useEffect(() => {
    if (!idKey) return;
    const controller = new AbortController();
    void (async () => {
      const wanted = new Set(idKey.split(",").map(Number));
      const persistentCache = readCache();
      const displayCache = { ...persistentCache };
      const supplied = publicCards.filter((card) => wanted.has(card.id));
      await resolveCards(supplied, displayCache, controller.signal);
      const suppliedIds = new Set(supplied.map((card) => card.id));
      const unresolved = new Set([...wanted].filter((id) => !suppliedIds.has(id)));
      if (unresolved.size) {
        const response = await fetch("/api/cards", { signal: controller.signal, cache: "force-cache" });
        if (response.ok) {
          const payload = await response.json() as unknown;
          const rows: CatalogCard[] = [];
          for (const row of collectRows(payload)) {
            const record = asRecord(row);
            if (!record) continue;
            const id = pickNumber(record);
            if (id === null || !unresolved.has(id)) continue;
            const explicit = pickUrl(record);
            if (explicit) displayCache[String(id)] = explicit;
            rows.push({ id, name: text(record, "name", "card_name", "Card Name"), number: text(record, "number", "collection_no", "Collection No."), expansion: text(record, "expansion", "Expansion"), sourceLink: text(record, "sourceLink", "link") });
          }
          await resolveCards(rows, displayCache, controller.signal);
          for (const id of unresolved) {
            const url = displayCache[String(id)];
            if (url) persistentCache[String(id)] = url;
          }
        }
      }
      localStorage.setItem(CACHE_KEY, JSON.stringify(persistentCache));
      setEntries(Object.entries(displayCache).map(([id, url]) => [Number(id), url]));
    })().catch(() => undefined);
    return () => controller.abort();
  }, [idKey, publicKey]);
  return useMemo(() => new Map(entries), [entries]);
}

export function cardArtUrl(cardId: number, explicit: string | null, catalog: CardArtCatalog): string | null {
  return explicit || catalog.get(cardId) || null;
}
