import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { OfficialScoreDashboard } from "./OfficialScoreDashboard";
import { officialScoreCsv, officialScoreDashboardData, parseOfficialScoreDashboardData } from "./official-score-data";

describe("official score dashboard", () => {
  it("renders exact official rows as a non-live snapshot with guard text", () => {
    const html = renderToStaticMarkup(<OfficialScoreDashboard />);

    expect(html).toContain("Pokémon official-row audit snapshot");
    expect(html).toContain("AUTO REFRESH OFF");
    expect(html).toContain("This is not a live feed");
    expect(html).toContain("2026-07-28 22:12Z");
    expect(html).toContain("844.4");
    expect(html).toContain("row 55056992");
    expect(html).toContain("RMY Souta");
    expect(html).toContain("row 55057790");
    expect(html).toContain("775.0");
    expect(html).toContain("Observable V4");
    expect(html).toContain("row 55058197");
    expect(html).toContain("671.3");
    expect(html).toContain("High-vote Alakazam audit notebook");
    expect(html).toContain("PUBLIC NOTEBOOK ONLY");
    expect(html).toContain("not a row");
    expect(html).toContain("Missing legacy V8 slug");
    expect(html).toContain("NO-DELETE / NO-RECOVERY GUARD");
  });

  it("exports the same audited rows as CSV without inventing missing row ids or scores", () => {
    const csv = officialScoreCsv();
    const lines = csv.trim().split("\n");

    expect(lines[0]).toBe("status,lane,row_id,public_score,decision");
    expect(lines).toHaveLength(officialScoreDashboardData.rows.length + 1);
    expect(csv).toContain("COMPLETE,Owned high-water,55056992,844.4");
    expect(csv).toContain("COMPLETE,RMY Souta,55057790,775");
    expect(csv).toContain("COMPLETE,Observable V4,55058197,671.3");
    expect(csv).toContain("PUBLIC_NOTEBOOK_ONLY,High-vote Alakazam audit notebook,,,PUBLIC RUN SURFACE");
    expect(csv).toContain("HARD_RULE,Missing legacy V8 slug,,,FROZEN READ-ONLY");
  });

  it("accepts a verified imported snapshot but never enables automatic refresh", () => {
    const imported = parseOfficialScoreDashboardData({
      ...officialScoreDashboardData,
      capturedAt: "2026-07-30T00:00:00Z",
      sourceLabel: "verified JSON fixture",
    });

    expect(imported.dataMode).toBe("IMPORTED_SNAPSHOT");
    expect(imported.automaticRefresh).toBe(false);
    expect(imported.sourceLabel).toBe("verified JSON fixture");
  });
});
