import { z } from "zod";

export const cardInstanceSchema = z.object({
  playerIndex: z.number().int().min(0).max(1),
  serial: z.number().int().nonnegative(),
  cardId: z.number().int().nonnegative(),
  name: z.string().default("Unknown card"),
  zone: z.enum(["active", "bench", "hand", "deck", "discard", "prize", "looking", "unknown"]),
  slot: z.number().int().nonnegative().nullable().default(null),
  hp: z.number().int().nonnegative().nullable().default(null),
  maxHp: z.number().int().nonnegative().nullable().default(null),
  damage: z.number().int().nonnegative().default(0),
  energies: z.array(z.string()).default([]),
  tools: z.array(z.string()).default([]),
  status: z.array(z.string()).default([]),
  evolution: z.array(z.number().int().nonnegative()).default([]),
  imageUrl: z.string().url().nullable().default(null),
});

export const playerStateSchema = z.object({
  name: z.string(),
  active: cardInstanceSchema.nullable(),
  bench: z.array(cardInstanceSchema).max(5),
  hand: z.array(cardInstanceSchema).default([]),
  handCount: z.number().int().nonnegative(),
  deckCount: z.number().int().nonnegative(),
  prizeCount: z.number().int().nonnegative(),
  discard: z.array(cardInstanceSchema).default([]),
  supporterPlayed: z.boolean().default(false),
  retreated: z.boolean().default(false),
});

export const battleEventSchema = z.object({
  type: z.string(),
  actor: z.number().int().min(0).max(1).nullable().default(null),
  text: z.string(),
  cardKey: z.string().nullable().default(null),
});

export const decisionCandidateSchema = z.object({
  label: z.string(),
  score: z.number(),
  selected: z.boolean().default(false),
  reason: z.string().nullable().default(null),
  kind: z.string().nullable().default(null),
  cardId: z.number().int().nonnegative().nullable().default(null),
  serial: z.number().int().nonnegative().nullable().default(null),
});

export const selectedActionSchema = z.object({
  arrayIndex: z.number().int().nonnegative().nullable().default(null),
  optionIndex: z.number().int().nonnegative(),
  kind: z.string().default("UNKNOWN"),
  cardId: z.number().int().nonnegative().nullable().default(null),
  serial: z.number().int().nonnegative().nullable().default(null),
  effectSource: z.string().default(""),
  label: z.string().default(""),
});

export const decisionSchema = z.object({
  actor: z.number().int().min(0).max(1),
  goal: z.string().default("unrecorded"),
  chosen: z.string(),
  confidence: z.number().min(0).max(1).nullable().default(null),
  elapsedMs: z.number().nonnegative().nullable().default(null),
  candidates: z.array(decisionCandidateSchema).default([]),
  overlayVersion: z.string().default("1.0"),
  selectedAction: selectedActionSchema.nullable().default(null),
  selectedActions: z.array(selectedActionSchema).default([]),
  scores: z.record(z.string(), z.number()).default({}),
  flags: z.record(z.string(), z.boolean()).default({}),
  warnings: z.array(z.string()).default([]),
  alternatives: z.array(decisionCandidateSchema).default([]),
  boardDiff: z.array(z.string()).default([]),
  scoreSource: z.string().default("unknown"),
});

export const battleFrameSchema = z.object({
  frameId: z.number().int().nonnegative(),
  turn: z.number().int().nonnegative(),
  actionCount: z.number().int().nonnegative(),
  actingPlayer: z.number().int().min(0).max(1),
  phase: z.string().default("unknown"),
  players: z.tuple([playerStateSchema, playerStateSchema]),
  stadium: cardInstanceSchema.nullable().default(null),
  events: z.array(battleEventSchema).default([]),
  decision: decisionSchema.nullable().default(null),
  result: z.string().nullable().default(null),
});

export const battleReplaySchema = z.object({
  schemaVersion: z.literal("1.0"),
  replayId: z.string(),
  createdAt: z.string(),
  source: z.enum(["cabt", "kaggle", "demo", "unknown"]),
  hiddenInformationPolicy: z.enum(["player_view", "spectator", "unknown"]).default("unknown"),
  frames: z.array(battleFrameSchema).min(1),
});

export type CardInstance = z.infer<typeof cardInstanceSchema>;
export type BattleFrame = z.infer<typeof battleFrameSchema>;
export type BattleReplay = z.infer<typeof battleReplaySchema>;
export type DecisionCandidate = z.infer<typeof decisionCandidateSchema>;
export type SelectedAction = z.infer<typeof selectedActionSchema>;

export function cardKey(card: CardInstance): string {
  return `${card.playerIndex}:${card.serial}`;
}
