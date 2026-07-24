import { describe, expect, it } from "vitest";
import { decodeDragPayload, encodeDragPayload, moveCardBefore, reconcileDeckOrder, uniqueCardOrder } from "./deck-dnd";

describe("deck drag operations", () => {
  it("deduplicates imported deck order without losing first appearance", () => {
    expect(uniqueCardOrder([3, 1, 3, 2, 1])).toEqual([3, 1, 2]);
  });

  it("reconciles order against cards currently in the deck", () => {
    expect(reconcileDeckOrder([4, 2, 9], [2, 3, 4])).toEqual([4, 2, 3]);
  });

  it("inserts a catalog card before the hovered deck row", () => {
    expect(moveCardBefore([1, 2, 3], 8, 2)).toEqual([1, 8, 2, 3]);
  });

  it("reorders an existing deck row and moves to end", () => {
    expect(moveCardBefore([1, 2, 3], 3, 1)).toEqual([3, 1, 2]);
    expect(moveCardBefore([1, 2, 3], 1, null)).toEqual([2, 3, 1]);
  });

  it("round-trips safe drag payloads and rejects malformed input", () => {
    const encoded = encodeDragPayload({ origin: "catalog", cardId: 666 });
    expect(decodeDragPayload(encoded)).toEqual({ origin: "catalog", cardId: 666 });
    expect(decodeDragPayload("{}" )).toBeNull();
    expect(decodeDragPayload("not-json")).toBeNull();
  });
});
