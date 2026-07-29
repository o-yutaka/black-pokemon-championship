export type OfficialRowStatus = "COMPLETE" | "PUBLIC_NOTEBOOK_ONLY" | "HARD_RULE";
export type OfficialScoreDataMode = "STATIC_SNAPSHOT" | "IMPORTED_SNAPSHOT";

export type OfficialScoreCard = {
  id: string;
  title: string;
  value: number;
  subtitle: string;
  tone: "green" | "blue" | "red";
};

export type OfficialScoreRow = {
  id: string;
  status: OfficialRowStatus;
  lane: string;
  rowId: number | null;
  publicScore: number | null;
  decision: string;
};

export type OfficialScoreDashboardData = {
  title: string;
  subtitle: string;
  capturedAt: string;
  sourceLabel: string;
  dataMode: OfficialScoreDataMode;
  automaticRefresh: false;
  cards: OfficialScoreCard[];
  rows: OfficialScoreRow[];
  guardNote: string;
};

export const officialScoreDashboardData: OfficialScoreDashboardData = {
  title: "Pokémon official-row audit snapshot",
  subtitle: "Exact official score boundaries, public-notebook separation, and no-delete guard. This is not a live feed.",
  capturedAt: "2026-07-28T22:12:00Z",
  sourceLabel: "Manual audit snapshot supplied on 2026-07-28",
  dataMode: "STATIC_SNAPSHOT",
  automaticRefresh: false,
  cards: [
    {
      id: "owned-high-water",
      title: "Owned high-water",
      value: 844.4,
      subtitle: "row 55056992 · COMPLETE",
      tone: "green",
    },
    {
      id: "best-v8-lineage",
      title: "Best V8 lineage row",
      value: 728.8,
      subtitle: "row 54874835 · COMPLETE",
      tone: "blue",
    },
    {
      id: "newest-drifted-branch",
      title: "Newest drifted branch",
      value: 671.3,
      subtitle: "row 55058197 · COMPLETE",
      tone: "red",
    },
  ],
  rows: [
    {
      id: "owned-high-water-row",
      status: "COMPLETE",
      lane: "Owned high-water",
      rowId: 55056992,
      publicScore: 844.4,
      decision: "RETAIN · current official high-water at capture time",
    },
    {
      id: "rmy-souta",
      status: "COMPLETE",
      lane: "RMY Souta",
      rowId: 55057790,
      publicScore: 775.0,
      decision: "WEAKER · do not stack unchanged",
    },
    {
      id: "best-v8-lineage-row",
      status: "COMPLETE",
      lane: "Best V8 lineage",
      rowId: 54874835,
      publicScore: 728.8,
      decision: "REFERENCE · preserve lineage boundary",
    },
    {
      id: "observable-v4",
      status: "COMPLETE",
      lane: "Observable V4",
      rowId: 55058197,
      publicScore: 671.3,
      decision: "DRIFTED · weaker than retained high-water",
    },
    {
      id: "alakazam-notebook",
      status: "PUBLIC_NOTEBOOK_ONLY",
      lane: "High-vote Alakazam audit notebook",
      rowId: null,
      publicScore: null,
      decision: "PUBLIC RUN SURFACE · not an official score row",
    },
    {
      id: "missing-legacy-v8",
      status: "HARD_RULE",
      lane: "Missing legacy V8 slug",
      rowId: null,
      publicScore: null,
      decision: "FROZEN READ-ONLY · no-delete / no-recovery guard",
    },
  ],
  guardNote: "This snapshot changes no policy code and creates no official submission. Replace it only with a newly verified audit JSON.",
};

function csvCell(value: string | number | null): string {
  if (value === null) return "";
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function officialScoreCsv(data: OfficialScoreDashboardData = officialScoreDashboardData): string {
  const header = ["status", "lane", "row_id", "public_score", "decision"];
  const lines = data.rows.map((row) => [
    row.status,
    row.lane,
    row.rowId,
    row.publicScore,
    row.decision,
  ].map(csvCell).join(","));
  return [header.join(","), ...lines].join("\n") + "\n";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function parseOfficialScoreDashboardData(value: unknown): OfficialScoreDashboardData {
  if (!isRecord(value)) throw new Error("監査JSONの先頭はobjectである必要があります");
  if (typeof value.title !== "string" || typeof value.subtitle !== "string") throw new Error("title / subtitleが必要です");
  if (typeof value.capturedAt !== "string" || Number.isNaN(Date.parse(value.capturedAt))) throw new Error("capturedAtはISO日時で指定してください");
  if (typeof value.sourceLabel !== "string") throw new Error("sourceLabelが必要です");
  if (!Array.isArray(value.cards) || !Array.isArray(value.rows)) throw new Error("cards / rows配列が必要です");

  const cards = value.cards.map((raw, index): OfficialScoreCard => {
    if (!isRecord(raw)) throw new Error(`cards[${index}]が不正です`);
    if (typeof raw.id !== "string" || typeof raw.title !== "string" || typeof raw.value !== "number" || typeof raw.subtitle !== "string") throw new Error(`cards[${index}]の必須項目が不足しています`);
    if (!['green', 'blue', 'red'].includes(String(raw.tone))) throw new Error(`cards[${index}].toneが不正です`);
    return { id: raw.id, title: raw.title, value: raw.value, subtitle: raw.subtitle, tone: raw.tone as OfficialScoreCard["tone"] };
  });

  const rows = value.rows.map((raw, index): OfficialScoreRow => {
    if (!isRecord(raw)) throw new Error(`rows[${index}]が不正です`);
    if (!['COMPLETE', 'PUBLIC_NOTEBOOK_ONLY', 'HARD_RULE'].includes(String(raw.status))) throw new Error(`rows[${index}].statusが不正です`);
    if (typeof raw.id !== "string" || typeof raw.lane !== "string" || typeof raw.decision !== "string") throw new Error(`rows[${index}]の必須項目が不足しています`);
    if (raw.rowId !== null && typeof raw.rowId !== "number") throw new Error(`rows[${index}].rowIdが不正です`);
    if (raw.publicScore !== null && typeof raw.publicScore !== "number") throw new Error(`rows[${index}].publicScoreが不正です`);
    return { id: raw.id, status: raw.status as OfficialRowStatus, lane: raw.lane, rowId: raw.rowId as number | null, publicScore: raw.publicScore as number | null, decision: raw.decision };
  });

  return {
    title: value.title,
    subtitle: value.subtitle,
    capturedAt: value.capturedAt,
    sourceLabel: value.sourceLabel,
    dataMode: "IMPORTED_SNAPSHOT",
    automaticRefresh: false,
    cards,
    rows,
    guardNote: typeof value.guardNote === "string" ? value.guardNote : officialScoreDashboardData.guardNote,
  };
}
