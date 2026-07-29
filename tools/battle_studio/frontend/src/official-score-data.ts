export type OfficialRowStatus = "COMPLETE" | "PUBLIC_NOTEBOOK_ONLY" | "HARD_RULE";

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
  refreshedAt: string;
  cards: OfficialScoreCard[];
  rows: OfficialScoreRow[];
  guardNote: string;
};

export const officialScoreDashboardData: OfficialScoreDashboardData = {
  title: "Live Pokémon official-row dashboard",
  subtitle: "High-vote public notebook surface, exact official score boundaries, and no-delete guard.",
  refreshedAt: "2026-07-28T22:12:00Z",
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
      decision: "RETAIN · current official high-water",
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
  guardNote: "This visual changes no policy code and creates no official submission. It keeps the public notebook honest, current, and identity-safe.",
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
