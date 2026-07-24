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
  reason: z.string().nullable().optional(),
  kind: z.string().nullable().optional(),
  cardId: z.number().int().nonnegative().nullable().optional(),
  serial: z.number().int().nonnegative().nullable().optional(),
});

export const selectedActionSchema = z.object({
  arrayIndex: z.number().int().nonnegative().nullable().optional(),
  optionIndex: z.number().int().nonnegative(),
  kind: z.string().optional(),
  cardId: z.number().int().nonnegative().nullable().optional(),
  serial: z.number().int().nonnegative().nullable().optional(),
  effectSource: z.string().optional(),
  label: z.string().optional(),
});

export type SearchTreeStatus = "root" | "available" | "expanded" | "selected" | "pruned";
export type SearchTreeNode = {
  id: string;
  label: string;
  status: SearchTreeStatus;
  ev: number | null;
  visits: number | null;
  mean: number | null;
  worst: number | null;
  best: number | null;
  reason: string | null;
  children: SearchTreeNode[];
};

export const searchTreeNodeSchema: z.ZodType<SearchTreeNode> = z.lazy(() => z.object({
  id: z.string(),
  label: z.string(),
  status: z.enum(["root", "available", "expanded", "selected", "pruned"]).default("available"),
  ev: z.number().nullable().default(null),
  visits: z.number().int().nonnegative().nullable().default(null),
  mean: z.number().nullable().default(null),
  worst: z.number().nullable().default(null),
  best: z.number().nullable().default(null),
  reason: z.string().nullable().default(null),
  children: z.array(searchTreeNodeSchema).default([]),
}));

export const rejectedBranchSchema = z.object({
  label: z.string(),
  reason: z.string().default("理由未提供"),
  evidence: z.array(z.string()).default([]),
  metrics: z.record(z.string(), z.union([z.string(), z.number()])).default({}),
  killedBy: z.array(z.string()).default([]),
});

export const policyTraceSchema = z.object({
  name: z.string(),
  status: z.enum(["PASS", "FAIL", "HOLD", "SKIP"]).default("SKIP"),
  score: z.number().default(0),
  reason: z.string().default(""),
});

export const routeSchema = z.object({
  name: z.string().default("Win Route"),
  steps: z.array(z.string()).default([]),
  currentStep: z.number().int().nonnegative().default(0),
});

export const prizePlannerSchema = z.object({
  neededAttacks: z.number().nullable().default(null),
  expectedAttacks: z.number().nullable().default(null),
  risk: z.number().min(0).max(1).nullable().default(null),
  alternatives: z.array(decisionCandidateSchema).default([]),
});

export const boardAnalysisSchema = z.object({
  total: z.number().nullable().default(null),
  components: z.record(z.string(), z.number()).default({}),
  threatMap: z.record(z.string(), z.number()).default({}),
});

export const counterfactualSchema = z.object({
  label: z.string(),
  baselineWinRate: z.number().min(0).max(1).nullable().default(null),
  alternativeWinRate: z.number().min(0).max(1).nullable().default(null),
  reason: z.string().default(""),
});

export const causalityGraphSchema = z.object({
  nodes: z.array(z.string()).default([]),
  edges: z.array(z.object({ from: z.string(), to: z.string(), label: z.string().optional() })).default([]),
});

const ledgerValueSchema = z.union([z.string(), z.number(), z.boolean(), z.null()]);

export const decisionSchema = z.object({
  actor: z.number().int().min(0).max(1),
  decisionId: z.string().optional(),
  goal: z.string().default("unrecorded"),
  chosen: z.string(),
  confidence: z.number().min(0).max(1).nullable().default(null),
  expectedWinRate: z.number().min(0).max(1).nullable().optional(),
  elapsedMs: z.number().nonnegative().nullable().default(null),
  priority: z.array(z.string()).optional(),
  candidates: z.array(decisionCandidateSchema).default([]),
  overlayVersion: z.string().optional(),
  selectedAction: selectedActionSchema.nullable().optional(),
  selectedActions: z.array(selectedActionSchema).optional(),
  scores: z.record(z.string(), z.number()).optional(),
  flags: z.record(z.string(), z.boolean()).optional(),
  warnings: z.array(z.string()).optional(),
  alternatives: z.array(decisionCandidateSchema).optional(),
  boardDiff: z.array(z.string()).optional(),
  scoreSource: z.string().optional(),
  searchTree: searchTreeNodeSchema.nullable().optional(),
  rejectedBranches: z.array(rejectedBranchSchema).optional(),
  policyTrace: z.array(policyTraceSchema).optional(),
  boardAnalysis: boardAnalysisSchema.optional(),
  route: routeSchema.optional(),
  prizePlanner: prizePlannerSchema.optional(),
  heatmap: z.record(z.string(), z.number()).optional(),
  policyBattle: z.record(z.string(), z.number()).optional(),
  counterfactuals: z.array(counterfactualSchema).optional(),
  causalityGraph: causalityGraphSchema.optional(),
  hiddenBelief: z.record(z.string(), z.number().min(0).max(1)).optional(),
  decisionDiff: z.object({
    previous: z.string().default(""),
    current: z.string().default(""),
    why: z.string().default(""),
    delta: z.number().nullable().default(null),
  }).optional(),
  truthLedger: z.record(z.string(), ledgerValueSchema).optional(),
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
export type RejectedBranch = z.infer<typeof rejectedBranchSchema>;
export type PolicyTrace = z.infer<typeof policyTraceSchema>;

export function cardKey(card: CardInstance): string {
  return `${card.playerIndex}:${card.serial}`;
}
