import { officialScoreCsv, officialScoreDashboardData, type OfficialRowStatus, type OfficialScoreDashboardData } from "./official-score-data";
import "./official-score-dashboard.css";

const STATUS_LABELS: Record<OfficialRowStatus, string> = {
  COMPLETE: "COMPLETE",
  PUBLIC_NOTEBOOK_ONLY: "PUBLIC NOTEBOOK ONLY",
  HARD_RULE: "HARD RULE",
};

function refreshedLabel(value: string): string {
  return value.replace("T", " ").replace(":00Z", "Z");
}

function downloadCsv(data: OfficialScoreDashboardData): void {
  const blob = new Blob([officialScoreCsv(data)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "v8_live_score_dashboard.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function OfficialScoreDashboard({ data = officialScoreDashboardData }: { data?: OfficialScoreDashboardData }) {
  return (
    <article className="official-score-dashboard" aria-label="Live Pokémon official-row dashboard">
      <header className="official-score-head">
        <div>
          <div className="official-score-kicker"><span className="official-live-dot" />OFFICIAL ROW AUDIT</div>
          <h2>{data.title}</h2>
          <p>{data.subtitle}</p>
        </div>
        <div className="official-score-refresh">
          <span>LIVE SCORE REFRESH</span>
          <time dateTime={data.refreshedAt}>{refreshedLabel(data.refreshedAt)}</time>
          <button type="button" onClick={() => downloadCsv(data)}>CSVを書き出す</button>
        </div>
      </header>

      <section className="official-score-cards" aria-label="主要公式スコア">
        {data.cards.map((card) => (
          <article className={`official-score-card tone-${card.tone}`} key={card.id}>
            <span>{card.title}</span>
            <strong>{card.value.toFixed(1)}</strong>
            <small>{card.subtitle}</small>
          </article>
        ))}
      </section>

      <section className="official-score-table" aria-label="公式row監査一覧">
        <div className="official-score-table-head" aria-hidden="true">
          <span>STATUS</span><span>LANE</span><span>OFFICIAL ROW</span><span>DECISION</span>
        </div>
        {data.rows.map((row) => (
          <article className="official-score-row" key={row.id}>
            <div><span className={`official-status status-${row.status.toLowerCase()}`}>{STATUS_LABELS[row.status]}</span></div>
            <strong>{row.lane}</strong>
            <span className="official-row-value">
              <b>{row.rowId === null ? "not a row" : `row ${row.rowId}`}</b>
              <small>{row.publicScore === null ? "no score" : row.publicScore.toFixed(1)}</small>
            </span>
            <span className="official-row-decision">{row.decision}</span>
          </article>
        ))}
      </section>

      <footer className="official-score-guard">
        <span>NO-DELETE / NO-RECOVERY GUARD</span>
        <p>{data.guardNote}</p>
      </footer>
    </article>
  );
}

export function OfficialScoreDashboardDialog({ onClose }: { onClose: () => void }) {
  return (
    <div className="official-score-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="official-score-dialog" role="dialog" aria-modal="true" aria-label="公式スコア監査" onMouseDown={(event) => event.stopPropagation()}>
        <button className="official-score-close" type="button" onClick={onClose}>閉じる</button>
        <OfficialScoreDashboard />
      </section>
    </div>
  );
}
