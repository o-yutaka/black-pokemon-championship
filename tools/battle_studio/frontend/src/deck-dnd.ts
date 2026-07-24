export type DragOrigin = "catalog" | "deck";

export type DeckDragPayload = {
  origin: DragOrigin;
  cardId: number;
};

export function uniqueCardOrder(ids: Iterable<number>): number[] {
  const seen = new Set<number>();
  const result: number[] = [];
  for (const id of ids) {
    if (!Number.isInteger(id) || seen.has(id)) continue;
    seen.add(id);
    result.push(id);
  }
  return result;
}

export function reconcileDeckOrder(order: readonly number[], activeIds: Iterable<number>): number[] {
  const active = new Set(activeIds);
  const kept = order.filter((id, index) => active.has(id) && order.indexOf(id) === index);
  const seen = new Set(kept);
  for (const id of active) {
    if (!seen.has(id)) {
      kept.push(id);
      seen.add(id);
    }
  }
  return kept;
}

export function moveCardBefore(order: readonly number[], cardId: number, beforeId: number | null): number[] {
  const result = order.filter((id) => id !== cardId);
  if (beforeId === null || beforeId === cardId) {
    result.push(cardId);
    return result;
  }
  const index = result.indexOf(beforeId);
  if (index < 0) result.push(cardId);
  else result.splice(index, 0, cardId);
  return result;
}

export function encodeDragPayload(payload: DeckDragPayload): string {
  return JSON.stringify(payload);
}

export function decodeDragPayload(value: string): DeckDragPayload | null {
  try {
    const parsed = JSON.parse(value) as Partial<DeckDragPayload>;
    if ((parsed.origin !== "catalog" && parsed.origin !== "deck") || !Number.isInteger(parsed.cardId)) return null;
    return { origin: parsed.origin, cardId: parsed.cardId as number };
  } catch {
    return null;
  }
}
