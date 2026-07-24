import type { PickedFolder } from "./folderPicker";

export type AnalysisCatalogCard = {
  id: number;
  name: string;
  kind: string;
  stage: string;
  previous: string;
  basicEnergy: boolean;
  basicPokemon: boolean;
  ace: boolean;
};

export type DeckIntent = {
  winCondition: string;
  idealTurns: string[];
  aceReason: string;
  lossConditions: string[];
  invariants: string[];
};

export type MatchupMetric = {
  name: string;
  wins: number;
  losses: number;
  draws?: number;
  firstGames?: number;
  secondGames?: number;
  engineErrors?: number;
  timeouts?: number;
  ev?: number;
};

export type AnalysisSnapshot = {
  name: string;
  deckSha?: string;
  bundleSha?: string;
  matchups: MatchupMetric[];
};

export type EvaluationProvenance = {
  evaluationId: string;
  evaluatedAt: string;
  method: string;
  engineErrors: number;
  timeouts: number;
  smokePassed?: boolean;
  submissionFormatPassed?: boolean;
};

export type ReportSynergy = {
  severity: "info" | "warning" | "danger";
  title: string;
  detail: string;
  metric?: string;
};

export type AnalysisReport = {
  schemaVersion: "1.0";
  intent?: DeckIntent;
  current?: AnalysisSnapshot;
  candidate?: AnalysisSnapshot;
  evaluation?: EvaluationProvenance;
  synergy?: ReportSynergy[];
  hashes?: {
    policySha?: string;
    freezeSha?: string;
    engineSha?: string;
  };
};

export type AgentAnalysisContext = {
  report: AnalysisReport | null;
  reportSource: string | null;
  policySha: string | null;
  freezeSha: string | null;
  engineSha: string | null;
  bundleSha: string | null;
  bundledEngineSha: string | null;
};

export type DeckDiffItem = {
  cardId: number;
  name: string;
  delta: number;
};

export type SynergyWarning = {
  severity: "info" | "warning" | "danger";
  title: string;
  detail: string;
  source: "static" | "evaluation";
};

export type GateItem = {
  id: string;
  label: string;
  status: "pass" | "fail" | "pending";
  detail: string;
};

const ANALYSIS_FILENAMES = new Set([
  "black-analysis.json",
  "deck-analysis.json",
  "analysis/deck-analysis.json",
  "analysis/black-analysis.json",
]);

const POLICY_EXTENSIONS = [".py", ".json", ".yaml", ".yml", ".toml"];
const ANALYSIS_BASENAMES = new Set(["black-analysis.json", "deck-analysis.json", "deck-intent.json"]);

function object(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function number(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function parseMatchups(value: unknown): MatchupMetric[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((raw) => {
    const item = object(raw);
    if (!item || !text(item.name)) return [];
    return [{
      name: text(item.name),
      wins: number(item.wins),
      losses: number(item.losses),
      draws: number(item.draws),
      firstGames: number(item.firstGames),
      secondGames: number(item.secondGames),
      engineErrors: number(item.engineErrors),
      timeouts: number(item.timeouts),
      ev: typeof item.ev === "number" ? item.ev : undefined,
    }];
  });
}

function parseSnapshot(value: unknown): AnalysisSnapshot | undefined {
  const item = object(value);
  if (!item) return undefined;
  return {
    name: text(item.name, "名称未設定"),
    deckSha: text(item.deckSha) || undefined,
    bundleSha: text(item.bundleSha) || undefined,
    matchups: parseMatchups(item.matchups),
  };
}

export function parseAnalysisReport(value: unknown): AnalysisReport {
  const root = object(value);
  if (!root || root.schemaVersion !== "1.0") throw new Error("分析JSONのschemaVersionは1.0が必要です");
  const intentRaw = object(root.intent);
  const evaluationRaw = object(root.evaluation);
  const hashesRaw = object(root.hashes);
  const synergy = Array.isArray(root.synergy) ? root.synergy.flatMap((raw) => {
    const item = object(raw);
    const severity = text(item?.severity);
    if (!item || !["info", "warning", "danger"].includes(severity) || !text(item.title)) return [];
    return [{ severity: severity as ReportSynergy["severity"], title: text(item.title), detail: text(item.detail), metric: text(item.metric) || undefined }];
  }) : [];
  const report: AnalysisReport = {
    schemaVersion: "1.0",
    current: parseSnapshot(root.current),
    candidate: parseSnapshot(root.candidate),
    synergy,
  };
  if (intentRaw) report.intent = {
    winCondition: text(intentRaw.winCondition),
    idealTurns: stringList(intentRaw.idealTurns),
    aceReason: text(intentRaw.aceReason),
    lossConditions: stringList(intentRaw.lossConditions),
    invariants: stringList(intentRaw.invariants),
  };
  if (evaluationRaw) report.evaluation = {
    evaluationId: text(evaluationRaw.evaluationId),
    evaluatedAt: text(evaluationRaw.evaluatedAt),
    method: text(evaluationRaw.method),
    engineErrors: number(evaluationRaw.engineErrors),
    timeouts: number(evaluationRaw.timeouts),
    smokePassed: typeof evaluationRaw.smokePassed === "boolean" ? evaluationRaw.smokePassed : undefined,
    submissionFormatPassed: typeof evaluationRaw.submissionFormatPassed === "boolean" ? evaluationRaw.submissionFormatPassed : undefined,
  };
  if (hashesRaw) report.hashes = {
    policySha: text(hashesRaw.policySha) || undefined,
    freezeSha: text(hashesRaw.freezeSha) || undefined,
    engineSha: text(hashesRaw.engineSha) || undefined,
  };
  return report;
}

function hex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer), (value) => value.toString(16).padStart(2, "0")).join("");
}

export async function sha256(data: string | ArrayBuffer): Promise<string> {
  const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
  return hex(await crypto.subtle.digest("SHA-256", bytes));
}

export function canonicalDeck(ids: number[]): string {
  const counts = new Map<number, number>();
  ids.forEach((id) => counts.set(id, (counts.get(id) ?? 0) + 1));
  return [...counts.entries()].sort(([left], [right]) => left - right).map(([id, count]) => `${id},${count}`).join("\n") + "\n";
}

export function deckDiff(baseline: number[], candidate: number[], catalog: Map<number, AnalysisCatalogCard>): DeckDiffItem[] {
  const count = (ids: number[]) => {
    const result = new Map<number, number>();
    ids.forEach((id) => result.set(id, (result.get(id) ?? 0) + 1));
    return result;
  };
  const before = count(baseline);
  const after = count(candidate);
  return [...new Set([...before.keys(), ...after.keys()])].map((cardId) => ({
    cardId,
    name: catalog.get(cardId)?.name ?? `不明なカード #${cardId}`,
    delta: (after.get(cardId) ?? 0) - (before.get(cardId) ?? 0),
  })).filter((item) => item.delta !== 0).sort((left, right) => left.delta - right.delta || left.name.localeCompare(right.name));
}

export function matchupRate(metric: MatchupMetric): number | null {
  const total = metric.wins + metric.losses + (metric.draws ?? 0);
  return total ? (metric.wins + (metric.draws ?? 0) * 0.5) / total : null;
}

export function staticSynergyWarnings(ids: number[], catalog: Map<number, AnalysisCatalogCard>, report?: AnalysisReport | null): SynergyWarning[] {
  const cards = ids.map((id) => catalog.get(id)).filter((card): card is AnalysisCatalogCard => Boolean(card));
  const basicCount = cards.filter((card) => card.basicPokemon).length;
  const energyCount = cards.filter((card) => card.basicEnergy || /energy|エネルギー/i.test(`${card.kind} ${card.stage}`)).length;
  const aceCount = cards.filter((card) => card.ace).length;
  const rareCandyCount = cards.filter((card) => /rare candy|ふしぎなアメ/i.test(card.name)).length;
  const nameCounts = new Map<string, number>();
  cards.forEach((card) => nameCounts.set(card.name, (nameCounts.get(card.name) ?? 0) + 1));
  const result: SynergyWarning[] = [];
  if (basicCount > 0 && basicCount <= 4) result.push({ severity: "danger", title: "たね率が低い", detail: `たねポケモン ${basicCount}枚 / 60枚。初動事故の実測確認が必要です。`, source: "static" });
  else if (basicCount > 0 && basicCount <= 6) result.push({ severity: "warning", title: "たね枚数を確認", detail: `たねポケモン ${basicCount}枚 / 60枚。これは静的注意で、事故率の断定ではありません。`, source: "static" });
  if (energyCount > 0 && energyCount < 8) result.push({ severity: "warning", title: "エネルギー枚数が少ない", detail: `エネルギー分類 ${energyCount}枚。必要ターンまでの到達率を公式リプレイで確認してください。`, source: "static" });
  if (energyCount > 18) result.push({ severity: "info", title: "エネルギー比率が高い", detail: `エネルギー分類 ${energyCount}枚。過剰かどうかは対面別実測で判断してください。`, source: "static" });
  if (aceCount === 0) result.push({ severity: "info", title: "ACE SPEC未採用", detail: "ACE SPECが0枚です。意図的な不採用かDeck Intentを確認してください。", source: "static" });
  const stage2 = cards.filter((card) => /stage\s*2|2進化/i.test(`${card.stage} ${card.kind}`));
  for (const card of stage2) {
    if (!card.previous) continue;
    const previousCount = nameCounts.get(card.previous) ?? 0;
    if (previousCount + rareCandyCount === 0) result.push({ severity: "danger", title: `${card.name}の進化経路が見つからない`, detail: `進化元「${card.previous}」も、ふしぎなアメもデッキ内で検出できません。`, source: "static" });
  }
  for (const item of report?.synergy ?? []) result.push({ severity: item.severity, title: item.title, detail: item.metric ? `${item.detail}（${item.metric}）` : item.detail, source: "evaluation" });
  return result;
}

export function buildBundleGate(input: {
  total: number;
  validationOk: boolean;
  hasBasic: boolean;
  aceOk: boolean;
  bundleLoaded: boolean;
  currentDeckSha: string | null;
  context: AgentAnalysisContext | null;
  report: AnalysisReport | null;
}): GateItem[] {
  const { context, report } = input;
  const candidateDeckSha = report?.candidate?.deckSha;
  const hashMatch = Boolean(candidateDeckSha && input.currentDeckSha && candidateDeckSha === input.currentDeckSha);
  const engineCompatible = Boolean(context?.engineSha && (!context.bundledEngineSha || context.bundledEngineSha === context.engineSha));
  return [
    { id: "60", label: "60枚", status: input.total === 60 ? "pass" : "fail", detail: `${input.total}/60枚` },
    { id: "rules", label: "カード枚数ルール", status: input.validationOk ? "pass" : "fail", detail: input.validationOk ? "違反なし" : "修正が必要" },
    { id: "basic", label: "たねポケモン", status: input.hasBasic ? "pass" : "fail", detail: input.hasBasic ? "検出済み" : "未検出" },
    { id: "ace", label: "ACE SPEC", status: input.aceOk ? "pass" : "fail", detail: input.aceOk ? "1枚以下" : "上限超過" },
    { id: "format", label: "main.py / deck.csv", status: input.bundleLoaded ? "pass" : "pending", detail: input.bundleLoaded ? "Bundle登録済み" : "対戦AI未選択" },
    { id: "engine", label: "公式Engine整合", status: engineCompatible ? "pass" : context?.engineSha ? "fail" : "pending", detail: engineCompatible ? "SHA整合" : "未確認" },
    { id: "deck-sha", label: "Deck SHA", status: input.currentDeckSha ? "pass" : "pending", detail: input.currentDeckSha?.slice(0, 12) ?? "計算中" },
    { id: "policy-sha", label: "Policy SHA", status: context?.policySha ? "pass" : "pending", detail: context?.policySha?.slice(0, 12) ?? "未取得" },
    { id: "freeze-sha", label: "Freeze SHA", status: context?.freezeSha ? "pass" : "pending", detail: context?.freezeSha?.slice(0, 12) ?? "分析JSON未提供" },
    { id: "bundle-sha", label: "Bundle SHA", status: context?.bundleSha ? "pass" : "pending", detail: context?.bundleSha?.slice(0, 12) ?? "未取得" },
    { id: "report-hash", label: "評価対象Hash一致", status: candidateDeckSha ? (hashMatch ? "pass" : "fail") : "pending", detail: candidateDeckSha ? (hashMatch ? "現在の60枚と一致" : "評価結果が別デッキ") : "分析JSON未提供" },
    { id: "smoke", label: "公式Smoke", status: report?.evaluation?.smokePassed === true ? "pass" : report?.evaluation?.smokePassed === false ? "fail" : "pending", detail: report?.evaluation?.smokePassed === true ? "PASS" : "未確認" },
    { id: "submission", label: "提出形式", status: report?.evaluation?.submissionFormatPassed === true ? "pass" : report?.evaluation?.submissionFormatPassed === false ? "fail" : "pending", detail: report?.evaluation?.submissionFormatPassed === true ? "PASS" : "未確認" },
  ];
}

async function policySha(folder: PickedFolder): Promise<string | null> {
  const sources = folder.files.filter((entry) => {
    const lower = entry.path.toLowerCase();
    const base = lower.split("/").at(-1) ?? lower;
    if (ANALYSIS_BASENAMES.has(base) || lower.endsWith("/deck.csv") || base === "deck.csv") return false;
    if (lower.includes("/cg/") || base === "libcg.so") return false;
    return POLICY_EXTENSIONS.some((extension) => lower.endsWith(extension));
  }).sort((left, right) => left.path.localeCompare(right.path));
  if (!sources.length) return null;
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (const source of sources) {
    const path = new TextEncoder().encode(`${source.path}\0`);
    const data = new Uint8Array(await source.file.arrayBuffer());
    chunks.push(path, data, new Uint8Array([0]));
    total += path.length + data.length + 1;
  }
  const merged = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { merged.set(chunk, offset); offset += chunk.length; }
  return sha256(merged.buffer);
}

export async function inspectAgentAnalysis(folder: PickedFolder, runtime: { engineSha: string | null; bundleSha: string; bundledEngineSha?: string | null }): Promise<AgentAnalysisContext> {
  const reportEntry = folder.files.find((entry) => ANALYSIS_FILENAMES.has(entry.path.toLowerCase())) ?? folder.files.find((entry) => ANALYSIS_BASENAMES.has(entry.path.toLowerCase().split("/").at(-1) ?? ""));
  let report: AnalysisReport | null = null;
  if (reportEntry) report = parseAnalysisReport(JSON.parse(await reportEntry.file.text()));
  return {
    report,
    reportSource: reportEntry?.path ?? null,
    policySha: await policySha(folder),
    freezeSha: report?.hashes?.freezeSha ?? null,
    engineSha: runtime.engineSha,
    bundleSha: runtime.bundleSha,
    bundledEngineSha: runtime.bundledEngineSha ?? null,
  };
}
