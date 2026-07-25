import { battleFrameSchema, battleReplaySchema, cardKey, type BattleReplay } from "./types";

export class ReplayValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ReplayValidationError";
  }
}

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function unwrapInput(input: unknown): unknown {
  if (!isRecord(input)) return input;
  for (const key of ["replay", "data", "payload"] as const) {
    const child = input[key];
    if (!isRecord(child)) continue;
    if (Array.isArray(child.frames) || isRecord(child.frame) || child.type === "snapshot") return child;
  }
  return input;
}

function normalizedSource(value: unknown, root: JsonRecord): "cabt" | "kaggle" | "demo" | "unknown" {
  if (value === "cabt" || value === "kaggle" || value === "demo" || value === "unknown") return value;
  if (typeof root.publicProtocol === "string" || root.engine === "official-battle" || root.type === "snapshot") return "cabt";
  return "unknown";
}

function normalizedPolicy(value: unknown): "player_view" | "spectator" | "unknown" {
  return value === "player_view" || value === "spectator" || value === "unknown" ? value : "unknown";
}

function normalizeReplayShape(input: unknown): unknown {
  const rootValue = unwrapInput(input);
  const ready = battleReplaySchema.safeParse(rootValue);
  if (ready.success) return ready.data;

  if (Array.isArray(rootValue)) {
    return {
      schemaVersion: "1.0",
      replayId: "imported-replay",
      createdAt: new Date().toISOString(),
      source: "unknown",
      hiddenInformationPolicy: "unknown",
      frames: rootValue,
    };
  }

  if (!isRecord(rootValue)) return rootValue;

  let frames: unknown[] | null = null;
  if (Array.isArray(rootValue.frames)) frames = rootValue.frames;
  else if (isRecord(rootValue.frame)) frames = [rootValue.frame];
  else if (battleFrameSchema.safeParse(rootValue).success) frames = [rootValue];

  if (!frames) return rootValue;

  return {
    schemaVersion: "1.0",
    replayId:
      typeof rootValue.replayId === "string" ? rootValue.replayId
        : typeof rootValue.sessionId === "string" ? rootValue.sessionId
          : typeof rootValue.id === "string" ? rootValue.id
            : "imported-replay",
    createdAt: typeof rootValue.createdAt === "string" ? rootValue.createdAt : new Date().toISOString(),
    source: normalizedSource(rootValue.source, rootValue),
    hiddenInformationPolicy: normalizedPolicy(rootValue.hiddenInformationPolicy),
    frames,
  };
}

function friendlyValidationMessage(input: unknown, issues: Array<{ path: PropertyKey[]; message: string }>): string {
  const root = unwrapInput(input);
  const first = issues[0];
  const path = first?.path.map(String).join(".") ?? "";
  if (!isRecord(root) && !Array.isArray(root)) {
    return "このファイルは対戦記録JSONではありません。JSON形式のReplay・Snapshot・Frameを選んでください。";
  }
  if (path.startsWith("frames")) {
    return `対戦の場面データを読み込めませんでした（${path || "frames"}）。別形式のログではなく、Battle StudioのReplay・Snapshot・Frameを選んでください。`;
  }
  return "対戦記録として認識できませんでした。Replay全体、BridgeのSnapshot、Frame単体、またはframes配列のJSONに対応しています。";
}

export function parseReplay(input: unknown): BattleReplay {
  const normalized = normalizeReplayShape(input);
  const parsed = battleReplaySchema.safeParse(normalized);
  if (!parsed.success) {
    throw new ReplayValidationError(friendlyValidationMessage(input, parsed.error.issues));
  }

  for (const frame of parsed.data.frames) {
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
      if (seen.has(key)) {
        throw new ReplayValidationError(`場面${frame.frameId}に同じカードが重複しています（${key}）`);
      }
      seen.add(key);
    }
  }

  return parsed.data;
}

export async function readReplayFile(file: File): Promise<BattleReplay> {
  if (file.size > 25 * 1024 * 1024) {
    throw new ReplayValidationError("対戦記録が25MBを超えています。必要な対戦だけに絞ってください。");
  }

  let raw: unknown;
  try {
    raw = JSON.parse(await file.text());
  } catch {
    throw new ReplayValidationError("JSONとして開けませんでした。壊れていないJSONファイルを選んでください。");
  }
  return parseReplay(raw);
}
