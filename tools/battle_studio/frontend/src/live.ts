import type { PublicCardCatalogEntry } from "./cardArt";
import { battleFrameSchema, type BattleFrame } from "./types";

export type LiveStatus = "disconnected" | "connecting" | "connected" | "closed" | "error";
export type ViewMode = "player" | "simulator";
export type LiveControls = {
  canAdvance: boolean;
  simulatorAvailable: boolean;
  viewMode: ViewMode;
};
export type LiveSnapshot = {
  sessionId: string;
  engine: string;
  frame: BattleFrame;
  legalSelections: number[][];
  controls: LiveControls;
  cardCatalog: PublicCardCatalogEntry[];
  publicProtocol: string | null;
  hiddenInformationPolicy: "player_view" | "simulator_full" | "spectator" | "unknown";
};
export type LiveConnection = {
  sessionId: string;
  engine: string;
  step(selection?: number[]): void;
  setViewMode(mode: ViewMode): void;
  ping(): void;
  close(): void;
};
export type LiveSessionOptions = {
  engine?: "emulator" | "official" | "official-native";
  bundleId?: string;
  opponentBundleId?: string;
  engineId?: string;
  playerBundleId?: string;
  nativeOpponentBundleId?: string;
};

export function toWebSocketUrl(httpBase: string, wsPath: string): string {
  const base = new URL(httpBase);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  base.pathname = wsPath;
  base.search = "";
  base.hash = "";
  return base.toString();
}

function parsePublicCards(value: unknown): PublicCardCatalogEntry[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const card = item as Record<string, unknown>;
    if (!Number.isInteger(card.id) || Number(card.id) < 0 || typeof card.name !== "string") return [];
    return [{
      id: Number(card.id),
      name: card.name,
      number: typeof card.number === "string" ? card.number : "",
      expansion: typeof card.expansion === "string" ? card.expansion : "",
      sourceLink: typeof card.sourceLink === "string" ? card.sourceLink : "",
    }];
  });
}

export function parseLiveSnapshot(raw: unknown): LiveSnapshot | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (value.type !== "snapshot" || typeof value.sessionId !== "string" || typeof value.engine !== "string") return null;
  const frame = battleFrameSchema.parse(value.frame);
  const legalSelections = Array.isArray(value.legalSelections)
    ? value.legalSelections.filter((entry): entry is number[] => Array.isArray(entry) && entry.every((item) => Number.isInteger(item)))
    : [];
  const rawControls = value.controls && typeof value.controls === "object" ? value.controls as Record<string, unknown> : null;
  const viewMode: ViewMode = rawControls?.viewMode === "simulator" ? "simulator" : "player";
  const controls = {
    canAdvance: rawControls ? rawControls.canAdvance === true : legalSelections.length > 0,
    simulatorAvailable: rawControls?.simulatorAvailable === true,
    viewMode,
  };
  const hiddenInformationPolicy =
    value.hiddenInformationPolicy === "player_view"
    || value.hiddenInformationPolicy === "simulator_full"
    || value.hiddenInformationPolicy === "spectator"
      ? value.hiddenInformationPolicy
      : "unknown";
  return {
    sessionId: value.sessionId,
    engine: value.engine,
    frame,
    legalSelections,
    controls,
    cardCatalog: parsePublicCards(value.cardCatalog),
    publicProtocol: typeof value.publicProtocol === "string" ? value.publicProtocol : null,
    hiddenInformationPolicy,
  };
}

export async function connectLive(
  baseUrl: string,
  options: LiveSessionOptions,
  onSnapshot: (snapshot: LiveSnapshot) => void,
  onStatus: (status: LiveStatus) => void,
  onError: (message: string) => void,
): Promise<LiveConnection> {
  onStatus("connecting");
  const response = await fetch(new URL("/api/sessions", baseUrl), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });
  if (!response.ok) {
    const value = await response.json().catch(() => ({})) as Record<string, unknown>;
    throw new Error(String(value.detail ?? `ライブセッションの作成に失敗しました（HTTP ${response.status}）`));
  }
  const session = await response.json() as { sessionId: string; engine: string; wsPath: string };
  const socket = new WebSocket(toWebSocketUrl(baseUrl, session.wsPath));
  let publicControl = false;
  await new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error("WebSocketの接続が時間切れになりました")), 5000);
    socket.addEventListener("open", () => { window.clearTimeout(timer); onStatus("connected"); resolve(); }, { once: true });
    socket.addEventListener("error", () => { window.clearTimeout(timer); reject(new Error("WebSocketへ接続できません")); }, { once: true });
  });
  socket.addEventListener("message", (event) => {
    try {
      const message = JSON.parse(String(event.data)) as unknown;
      const snapshot = parseLiveSnapshot(message);
      if (snapshot) {
        publicControl = snapshot.publicProtocol !== null;
        onSnapshot(snapshot);
        return;
      }
      if (message && typeof message === "object" && (message as Record<string, unknown>).type === "error") {
        onError(String((message as Record<string, unknown>).detail ?? (message as Record<string, unknown>).code ?? "ライブエンジンでエラーが発生しました"));
      }
    } catch (error) {
      onError(error instanceof Error ? error.message : "ライブメッセージの形式が正しくありません");
    }
  });
  socket.addEventListener("close", () => onStatus("closed"));
  socket.addEventListener("error", () => onStatus("error"));
  return {
    sessionId: session.sessionId,
    engine: session.engine,
    step(selection) {
      if (socket.readyState !== WebSocket.OPEN) throw new Error("WebSocketが接続されていません");
      socket.send(JSON.stringify(publicControl ? { type: "advance" } : { type: "step", selection: selection ?? [0] }));
    },
    setViewMode(mode) {
      if (socket.readyState !== WebSocket.OPEN) throw new Error("WebSocketが接続されていません");
      socket.send(JSON.stringify({ type: "set_view_mode", mode }));
    },
    ping() {
      if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "ping" }));
    },
    close() {
      if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "close" }));
      else socket.close();
    },
  };
}

export function connectLiveEmulator(
  baseUrl: string,
  onSnapshot: (snapshot: LiveSnapshot) => void,
  onStatus: (status: LiveStatus) => void,
  onError: (message: string) => void,
): Promise<LiveConnection> {
  return connectLive(baseUrl, { engine: "emulator" }, onSnapshot, onStatus, onError);
}
