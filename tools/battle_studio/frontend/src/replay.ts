import { battleReplaySchema, cardKey, type BattleReplay } from "./types";

export class ReplayValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ReplayValidationError";
  }
}

export function parseReplay(input: unknown): BattleReplay {
  const parsed = battleReplaySchema.safeParse(input);
  if (!parsed.success) {
    throw new ReplayValidationError(parsed.error.issues.map((issue) => `${issue.path.join(".")}: ${issue.message}`).join("; "));
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
        throw new ReplayValidationError(`Frame ${frame.frameId} contains duplicate card instance ${key}`);
      }
      seen.add(key);
    }
  }

  return parsed.data;
}

export async function readReplayFile(file: File): Promise<BattleReplay> {
  if (file.size > 25 * 1024 * 1024) {
    throw new ReplayValidationError("Replay exceeds the 25 MB local viewer limit");
  }

  let raw: unknown;
  try {
    raw = JSON.parse(await file.text());
  } catch {
    throw new ReplayValidationError("Replay is not valid JSON");
  }
  return parseReplay(raw);
}
