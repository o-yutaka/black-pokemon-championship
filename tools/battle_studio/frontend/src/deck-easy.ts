import type { AgentAnalysisContext } from "./deck-analysis";

export const BUNDLE_DECK_EVENT = "black:bundle-deck";
export const PLAYER_BUNDLE_SELECTED_EVENT = "black:player-bundle-selected";
export const PLAYER_BUNDLE_UPDATED_EVENT = "black:player-bundle-updated";
export const APPLY_PLAYER_DECK_EVENT = "black:apply-player-deck";

export type BundleSummary = {
  id: string;
  filename: string;
  sha256: string;
  deckCount: number;
  uniqueCardIds: number;
  bundledEngineSha256?: string | null;
};

export type PlayerBundleDetail = {
  bundle: BundleSummary;
  deck: number[];
  canApplyDirectly: boolean;
  analysis?: AgentAnalysisContext | null;
};

export type ApplyPlayerDeckDetail = {
  deck: number[];
};

export function parseDeckCsv(text: string): number[] {
  const cells = text.replace(/^\uFEFF/, "").split(/[\s,]+/).map((value) => value.trim()).filter(Boolean);
  const values: number[] = [];
  for (const cell of cells) {
    const normalized = cell.toLowerCase().replace(/\s+/g, "_");
    if (!values.length && ["card_id", "cardid", "id"].includes(normalized)) continue;
    if (!/^\d+$/.test(cell) || Number(cell) <= 0) throw new Error(`カードIDではない値があります: ${cell}`);
    values.push(Number(cell));
  }
  if (values.length !== 60) throw new Error(`デッキCSVは60枚必要です（現在${values.length}枚）`);
  return values;
}

export function deckCsv(ids: number[]): string {
  if (ids.length !== 60 || ids.some((id) => !Number.isInteger(id) || id <= 0)) throw new Error("正しい60枚のカードIDが必要です");
  return `${ids.join("\n")}\n`;
}

export function dispatchBundleDeck(deck: number[]): void {
  window.dispatchEvent(new CustomEvent(BUNDLE_DECK_EVENT, { detail: deck }));
}

export function dispatchPlayerBundleSelected(detail: PlayerBundleDetail): void {
  window.dispatchEvent(new CustomEvent(PLAYER_BUNDLE_SELECTED_EVENT, { detail }));
}

export function dispatchPlayerBundleUpdated(detail: PlayerBundleDetail): void {
  window.dispatchEvent(new CustomEvent(PLAYER_BUNDLE_UPDATED_EVENT, { detail }));
}
