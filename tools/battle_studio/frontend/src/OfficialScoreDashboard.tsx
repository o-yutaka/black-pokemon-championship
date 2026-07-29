import { useRef, useState } from "react";
import { officialScoreCsv, officialScoreDashboardData, parseOfficialScoreDashboardData, type OfficialRowStatus, type OfficialScoreDashboardData } from "./official-score-data";
import "./official-score-dashboard.css";

const STATUS_LABELS: Record<OfficialRowStatus, string> = {
  COMPLETE: "COMPLETE",
  PUBLIC_NOTEBOOK_ONLY: "PUBLIC NOTEBOOK ONLY",
  HARD_RULE: "HARD RULE",
};

function capturedLabel(value: string): string {
  return value.replace("T", " ").replace(":00Z", "Z");
}

function snapshotAge(value: string): string {
  const ageMs = Date.now() - Date.parse(value);
  if (!Number.isFinite(ageMs) || ageMs < 0) return "時刻確認が必要";
  const hours = Math.floor(ageMs / 3_600_000);
  return hours < 24 ? `${hours}時間前` : `${Math.floor(hours / 24)}日前`;
}

function downloadCsv(data: OfficialScoreDashboardData): void {
  const blob = new Blob([officialScoreCsv(data)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "v8_official_score_snapshot.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function OfficialScoreDashboard({ data = officialScoreDashboardData, onImport }: { data?: OfficialScoreDashboardData; onImport?: () => void }) {
  return (
    <article className="official-score-dashboard" aria-label="Pokémon official-row audit snapshot">
      <header className="official-score-head">
        <div>
          <div className="official-score-kicker"><span className="official-snapshot-dot" />OFFICIAL ROW SNAPSHOT · AUTO REFRESH OFF</div>
          <h2>{data.title}</h2>
          <p>{data.subtitle}</p>
          <div className="official-snapshot-warning"><strong>{data.dataMode.replace("_", " ")}</strong><span>{data.sourceLabel}</span><span>取得後 {snapshotAge(data.capturedAt)} · 外部API未接続</span></div>
        </div>
        <div className="official-score-refresh">
          <span>CAPTURED AT</span>
          <time dateTime={data.capturedAt}>{capturedLabel(data.capturedAt)}</time>
          {onImport && <button type="button" onClick={onImport}>更新JSONを読み込む</button>}
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
  const [data, setData] = useState(officialScoreDashboardData);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const importFile = async (file?: File) => {
    if (!file) return;
    try {
      setData(parseOfficialScoreDashboardData(JSON.parse(await file.text())));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "監査JSONを読み込めませんでした");
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="official-score-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="official-score-dialog" role="dialog" aria-modal="true" aria-label="公式スコア監査スナップショット" onMouseDown={(event) => event.stopPropagation()}>
        <input ref={inputRef} className="file-input" type="file" accept="application/json,.json" onChange={(event) => void importFile(event.target.files?.[0])} />
        <button className="official-score-close" type="button" onClick={onClose}>閉じる</button>
        {error && <div className="official-score-import-error" role="alert">{error}</div>}
        <OfficialScoreDashboard data={data} onImport={() => inputRef.current?.click()} />
      </section>
    </div>
  );
}
