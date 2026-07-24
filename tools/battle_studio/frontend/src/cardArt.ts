import { useEffect, useMemo, useState } from "react";

export type CardArtCatalog = Map<number, string>;

type UnknownRecord = Record<string, unknown>;

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
  return Object.values(record).every((value) => asRecord(value)) ? Object.values(record) : [];
}

export function useCardArtCatalog(): CardArtCatalog {
  const [entries, setEntries] = useState<Array<[number, string]>>([]);
  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/cards", { signal: controller.signal, cache: "force-cache" })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error(`card catalog ${response.status}`)))
      .then((payload: unknown) => {
        const next = new Map<number, string>();
        for (const row of collectRows(payload)) {
          const record = asRecord(row);
          if (!record) continue;
          const cardId = pickNumber(record);
          const imageUrl = pickUrl(record);
          if (cardId !== null && imageUrl) next.set(cardId, imageUrl);
        }
        setEntries([...next.entries()]);
      })
      .catch(() => setEntries([]));
    return () => controller.abort();
  }, []);
  return useMemo(() => new Map(entries), [entries]);
}

export function cardArtUrl(cardId: number, explicit: string | null, catalog: CardArtCatalog): string | null {
  if (explicit) return explicit;
  return catalog.get(cardId) ?? null;
}
