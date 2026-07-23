import { battleFrameSchema, type BattleFrame } from "./types";

export type LiveStatus = "disconnected" | "connecting" | "connected" | "closed" | "error";
export type LiveSnapshot = { sessionId: string; engine: string; frame: BattleFrame; legalSelections: number[][] };
export type LiveConnection = { sessionId: string; engine: string; step(selection?: number[]): void; ping(): void; close(): void };
export type LiveSessionOptions = { engine?: "emulator" | "official"; bundleId?: string; opponentBundleId?: string };

export function toWebSocketUrl(httpBase: string, wsPath: string): string {
  const base = new URL(httpBase);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  base.pathname = wsPath;
  base.search = "";
  base.hash = "";
  return base.toString();
}

export function parseLiveSnapshot(raw: unknown): LiveSnapshot | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (value.type !== "snapshot" || typeof value.sessionId !== "string" || typeof value.engine !== "string") return null;
  const frame = battleFrameSchema.parse(value.frame);
  const legalSelections = Array.isArray(value.legalSelections)
    ? value.legalSelections.filter((entry): entry is number[] => Array.isArray(entry) && entry.every((item) => Number.isInteger(item)))
    : [];
  return { sessionId: value.sessionId, engine: value.engine, frame, legalSelections };
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
    body: JSON.stringify({ engine: options.engine ?? "emulator", bundleId: options.bundleId, opponentBundleId: options.opponentBundleId }),
  });
  if (!response.ok) {
    const value = await response.json().catch(() => ({})) as Record<string, unknown>;
    throw new Error(String(value.detail ?? `Live session failed: HTTP ${response.status}`));
  }
  const session = await response.json() as { sessionId: string; engine: string; wsPath: string };
  const socket = new WebSocket(toWebSocketUrl(baseUrl, session.wsPath));
  await new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error("WebSocket open timeout")), 5000);
    socket.addEventListener("open", () => { window.clearTimeout(timer); onStatus("connected"); resolve(); }, { once: true });
    socket.addEventListener("error", () => { window.clearTimeout(timer); reject(new Error("WebSocket connection failed")); }, { once: true });
  });
  socket.addEventListener("message", (event) => {
    try {
      const message = JSON.parse(String(event.data)) as unknown;
      const snapshot = parseLiveSnapshot(message);
      if (snapshot) { onSnapshot(snapshot); return; }
      if (message && typeof message === "object" && (message as Record<string, unknown>).type === "error") {
        onError(String((message as Record<string, unknown>).detail ?? (message as Record<string, unknown>).code ?? "Live engine error"));
      }
    } catch (error) {
      onError(error instanceof Error ? error.message : "Invalid live message");
    }
  });
  socket.addEventListener("close", () => onStatus("closed"));
  socket.addEventListener("error", () => onStatus("error"));
  return {
    sessionId: session.sessionId,
    engine: session.engine,
    step(selection = [0]) { if (socket.readyState !== WebSocket.OPEN) throw new Error("WebSocket is not open"); socket.send(JSON.stringify({ type: "step", selection })); },
    ping() { if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "ping" })); },
    close() { if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "close" })); else socket.close(); },
  };
}

export function connectLiveEmulator(baseUrl: string, onSnapshot: (snapshot: LiveSnapshot) => void, onStatus: (status: LiveStatus) => void, onError: (message: string) => void): Promise<LiveConnection> {
  return connectLive(baseUrl, { engine: "emulator" }, onSnapshot, onStatus, onError);
}
