/** @vitest-environment happy-dom */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DeckBuilder, type CatalogCard } from "./DeckBuilder";

const cards: CatalogCard[] = [
  { id: 1, name: "Test Basic", expansion: "TST", number: "1", kind: "Pokémon", stage: "Basic", previous: "", hp: "60", type: "Psychic", rule: "", moves: [], basicEnergy: false, basicPokemon: true, ace: false },
  { id: 2, name: "Test Trainer", expansion: "TST", number: "2", kind: "Trainer", stage: "Item", previous: "", hp: "", type: "", rule: "", moves: [], basicEnergy: false, basicPokemon: false, ace: false },
];

function pointer(type: string, init: PointerEventInit): PointerEvent {
  return new PointerEvent(type, { bubbles: true, cancelable: true, pointerType: "touch", ...init });
}

describe("DeckBuilder touch drag UI", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({ ok: true, cards }),
    })));
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    await act(async () => {
      root.render(<DeckBuilder importedDeck={null} />);
      await Promise.resolve();
      await Promise.resolve();
    });
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
    document.body.className = "";
  });

  it("adds a catalog card by dragging its handle into MY DECK on touch", async () => {
    const handle = host.querySelector<HTMLButtonElement>('[aria-label="Test Basicをドラッグしてデッキへ追加"]');
    const zone = host.querySelector<HTMLElement>('[data-deck-drop-zone="true"]');
    expect(handle).not.toBeNull();
    expect(zone).not.toBeNull();
    vi.spyOn(document, "elementFromPoint").mockReturnValue(zone);

    await act(async () => {
      handle!.dispatchEvent(pointer("pointerdown", { pointerId: 7, clientX: 10, clientY: 10 }));
      window.dispatchEvent(pointer("pointermove", { pointerId: 7, clientX: 240, clientY: 320 }));
      window.dispatchEvent(pointer("pointerup", { pointerId: 7, clientX: 240, clientY: 320 }));
    });

    const row = host.querySelector<HTMLElement>('[data-deck-row-id="1"]');
    expect(row).not.toBeNull();
    expect(row?.textContent).toContain("Test Basic");
    expect(row?.textContent).toContain("1");
    expect(document.body.classList.contains("deck-dragging")).toBe(false);
  });

  it("reorders deck rows by dragging a deck handle before another row on touch", async () => {
    await act(async () => {
      root.render(<DeckBuilder importedDeck={[1, 2]} />);
      await Promise.resolve();
    });
    const rowOne = host.querySelector<HTMLElement>('[data-deck-row-id="1"]');
    const handleTwo = host.querySelector<HTMLButtonElement>('[aria-label="Test Trainerをドラッグして並べ替え"]');
    expect(rowOne).not.toBeNull();
    expect(handleTwo).not.toBeNull();
    vi.spyOn(document, "elementFromPoint").mockReturnValue(rowOne);

    await act(async () => {
      handleTwo!.dispatchEvent(pointer("pointerdown", { pointerId: 9, clientX: 20, clientY: 20 }));
      window.dispatchEvent(pointer("pointermove", { pointerId: 9, clientX: 80, clientY: 160 }));
      window.dispatchEvent(pointer("pointerup", { pointerId: 9, clientX: 80, clientY: 160 }));
    });

    const ids = [...host.querySelectorAll<HTMLElement>("[data-deck-row-id]")].map((row) => row.dataset.deckRowId);
    expect(ids).toEqual(["2", "1"]);
  });
});
