import { battleFrameSchema, battleReplaySchema, cardKey, type BattleFrame, type BattleReplay } from "./types";

export class ReplayValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ReplayValidationError";
  }
}

type JsonRecord = Record<string, unknown>;

const WRAPPER_KEYS = [
  "replay", "data", "payload", "result", "output", "response", "episode",
  "snapshot", "snapshots", "frame", "frames", "history", "timeline",
  "records", "steps", "states", "messages", "items",
] as const;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseEmbeddedJson(value: string): unknown | null {
  const text = value.trim();
  if (!text) return null;
  const candidates = [text];
  const objectStart = text.indexOf("{");
  const arrayStart = text.indexOf("[");
  const start = [objectStart, arrayStart].filter((index) => index >= 0).sort((a, b) => a - b)[0];
  if (start != null && start > 0) candidates.push(text.slice(start));
  for (const candidate of candidates) {
    try { return JSON.parse(candidate); }
    catch { /* try next representation */ }
  }
  return null;
}

function metadataRoot(input: unknown): JsonRecord {
  if (isRecord(input)) return input;
  return {};
}

function normalizedSource(value: unknown, root: JsonRecord): "cabt" | "kaggle" | "demo" | "unknown" {
  if (value === "cabt" || value === "kaggle" || value === "demo" || value === "unknown") return value;
  if (typeof root.publicProtocol === "string" || root.engine === "official-battle" || root.type === "snapshot") return "cabt";
  return "unknown";
}

function normalizedPolicy(value: unknown): "player_view" | "spectator" | "unknown" {
  return value === "player_view" || value === "spectator" || value === "unknown" ? value : "unknown";
}

function collectFrames(input: unknown, depth = 0, visited = new Set<object>()): BattleFrame[] {
  if (depth > 8) return [];

  const direct = battleFrameSchema.safeParse(input);
  if (direct.success) return [direct.data];

  if (typeof input === "string") {
    const embedded = parseEmbeddedJson(input);
    return embedded === null ? [] : collectFrames(embedded, depth + 1, visited);
  }

  if (Array.isArray(input)) {
    return input.flatMap((item) => collectFrames(item, depth + 1, visited));
  }

  if (!isRecord(input) || visited.has(input)) return [];
  visited.add(input);

  const preferred: unknown[] = [];
  const remaining: unknown[] = [];
  for (const [key, value] of Object.entries(input)) {
    if ((WRAPPER_KEYS as readonly string[]).includes(key)) preferred.push(value);
    else remaining.push(value);
  }

  const found = [...preferred, ...remaining].flatMap((value) => collectFrames(value, depth + 1, visited));
  const unique = new Map<number, BattleFrame>();
  for (const frame of found) unique.set(frame.frameId, frame);
  return [...unique.values()].sort((left, right) => left.frameId - right.frameId);
}

function normalizeReplayShape(input: unknown): BattleReplay | null {
  const ready = battleReplaySchema.safeParse(input);
  if (ready.success) return ready.data;

  const frames = collectFrames(input);
  if (!frames.length) return null;

  const root = metadataRoot(input);
  return battleReplaySchema.parse({
    schemaVersion: "1.0",
    replayId:
      typeof root.replayId === "string" ? root.replayId
        : typeof root.sessionId === "string" ? root.sessionId
          : typeof root.episodeId === "string" || typeof root.episodeId === "number" ? String(root.episodeId)
            : typeof root.id === "string" || typeof root.id === "number" ? String(root.id)
              : `imported-${frames[0].frameId}-${frames.length}`,
    createdAt: typeof root.createdAt === "string" ? root.createdAt : new Date().toISOString(),
    source: normalizedSource(root.source, root),
    hiddenInformationPolicy: normalizedPolicy(root.hiddenInformationPolicy),
    frames,
  });
}

function assertUniqueCards(replay: BattleReplay): void {
  for (const frame of replay.frames) {
    const seen = new Set<string>();
    const visibleCards = [
      frame.players[0].active,
      ...frame.players[0].bench,
      ...frame.players[0].hand,
      ...frame.players[0].discard,
      frame.players[1].active,
      ...frame.players[1].bench,
      ...frame.players[1].hand,
      ...frame.players[1].discard,
      frame.stadium,
    ].filter((card) => card !== null);

    for (const card of visibleCards) {
      const key = cardKey(card);
      if (seen.has(key)) throw new ReplayValidationError(`場面${frame.frameId}に同じカードが重複しています（${key}）`);
      seen.add(key);
    }
  }
}

export function parseReplay(input: unknown): BattleReplay {
  const replay = normalizeReplayShape(input);
  if (!replay) {
    throw new ReplayValidationError("対戦場面を見つけられませんでした。Battle Studioの記録、Bridge Snapshot、CABTの場面ログを選んでください。");
  }
  assertUniqueCards(replay);
  return replay;
}

function parseFileText(text: string): unknown {
  const whole = parseEmbeddedJson(text);
  if (whole !== null) return whole;

  const rows = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const parsedRows = rows.flatMap((line) => {
    const value = parseEmbeddedJson(line);
    return value === null ? [] : [value];
  });
  if (parsedRows.length) return parsedRows;

  throw new ReplayValidationError("JSONまたは1行1JSONの対戦ログとして開けませんでした。");
}

export async function readReplayFile(file: File): Promise<BattleReplay> {
  if (file.size > 50 * 1024 * 1024) {
    throw new ReplayValidationError("対戦記録が50MBを超えています。必要な対戦だけに絞ってください。");
  }
  return parseReplay(parseFileText(await file.text()));
}
