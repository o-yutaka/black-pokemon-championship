export type EngineArtifact = { id: string; filename: string; sha256: string; sourceKind: string; compiler: string | null };
export type BundleArtifact = { id: string; filename: string; sha256: string; deckCount: number; uniqueCardIds: number; memberCount: number; bundledEngineSha256: string | null };
export type CardMove = { name: string; cost: string; damage: string; text: string };
export type CardRecord = {
  cardId: number; name: string; expansion: string; collectionNo: string; stageOrType: string; rule: string; category: string;
  previousStage: string; hp: number | null; pokemonType: string; weakness: string; resistance: string; retreat: string;
  link: string; moves: CardMove[]; basicEnergy: boolean; aceSpec: boolean;
};

async function parseResponse<T>(response: Response): Promise<T> {
  const value = await response.json().catch(() => null) as { detail?: string } | null;
  if (!response.ok) throw new Error(value?.detail || `HTTP ${response.status}`);
  return value as T;
}

export function liveBaseUrl(): string {
  return import.meta.env.VITE_LIVE_BASE_URL || window.location.origin;
}

export async function uploadEngine(file: File): Promise<EngineArtifact> {
  const body = new FormData(); body.append("file", file);
  const response = await fetch(new URL("/api/artifacts/engine", liveBaseUrl()), { method: "POST", body });
  return (await parseResponse<{ engine: EngineArtifact }>(response)).engine;
}

export async function uploadBundle(file: File, engineId?: string): Promise<{ bundle: BundleArtifact; deck: number[] }> {
  const body = new FormData(); body.append("file", file);
  const url = new URL("/api/artifacts/bundles", liveBaseUrl());
  if (engineId) url.searchParams.set("engine_id", engineId);
  const response = await fetch(url, { method: "POST", body });
  return parseResponse(response);
}

export async function uploadCardCatalog(files: File[]): Promise<{ cardCount: number; attackCount: number }> {
  const body = new FormData(); files.forEach((file) => body.append("files", file));
  const response = await fetch(new URL("/api/artifacts/cards", liveBaseUrl()), { method: "POST", body });
  return (await parseResponse<{ cards: { cardCount: number; attackCount: number } }>(response)).cards;
}

export async function fetchCards(): Promise<CardRecord[]> {
  const response = await fetch(new URL("/api/cards?limit=5000", liveBaseUrl()), { cache: "no-store" });
  return (await parseResponse<{ cards: CardRecord[] }>(response)).cards;
}
