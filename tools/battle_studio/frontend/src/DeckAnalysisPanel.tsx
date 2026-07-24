import { useMemo, useRef } from "react";
import { buildBundleGate, deckDiff, matchupRate, parseAnalysisReport, staticSynergyWarnings, type AgentAnalysisContext, type AnalysisCatalogCard, type AnalysisReport, type GateItem } from "./deck-analysis";
import "./deck-analysis.css";

type Props = {
  baselineDeck: number[];
  candidateDeck: number[];
  catalog: Map<number, AnalysisCatalogCard>;
  selectedName: string | null;
  baselineDeckSha: string | null;
  candidateDeckSha: string | null;
  context: AgentAnalysisContext | null;
  report: AnalysisReport | null;
  total: number;
  validationOk: boolean;
  hasBasic: boolean;
  aceOk: boolean;
  onReport(report: AnalysisReport, source: string): void;
  onPromoteBaseline(): void;
};

function short(value?: string | null): string {
  return value ? value.slice(0, 12) : "—";
}

function GateRow({ item }: { item: GateItem }) {
  return <div className={`analysis-gate-row gate-${item.status}`}><span>{item.status === "pass" ? "✓" : item.status === "fail" ? "×" : "…"}</span><strong>{item.label}</strong><small>{item.detail}</small></div>;
}

function rateText(wins: number, losses: number, draws = 0): string {
  const total = wins + losses + draws;
  if (!total) return "未計測";
  return `${(((wins + draws * 0.5) / total) * 100).toFixed(1)}%`;
}

export function DeckAnalysisPanel(props: Props) {
  const reportRef = useRef<HTMLInputElement>(null);
  const diff = useMemo(() => deckDiff(props.baselineDeck, props.candidateDeck, props.catalog), [props.baselineDeck, props.candidateDeck, props.catalog]);
  const warnings = useMemo(() => staticSynergyWarnings(props.candidateDeck, props.catalog, props.report), [props.candidateDeck, props.catalog, props.report]);
  const gates = useMemo(() => buildBundleGate({ total: props.total, validationOk: props.validationOk, hasBasic: props.hasBasic, aceOk: props.aceOk, bundleLoaded: Boolean(props.selectedName), currentDeckSha: props.candidateDeckSha, context: props.context, report: props.report }), [props.total, props.validationOk, props.hasBasic, props.aceOk, props.selectedName, props.candidateDeckSha, props.context, props.report]);
  const allGreen = gates.every((item) => item.status === "pass");
  const current = props.report?.current;
  const candidate = props.report?.candidate;
  const matchupNames = [...new Set([...(current?.matchups ?? []).map((item) => item.name), ...(candidate?.matchups ?? []).map((item) => item.name)])];

  const importReport = async (file?: File) => {
    if (!file) return;
    props.onReport(parseAnalysisReport(JSON.parse(await file.text())), file.name);
  };

  return <aside className="deck-analysis-panel" aria-label="BLACKデッキ分析">
    <header className="analysis-head"><div><span>BLACK ANALYSIS</span><h3>デッキ分析</h3><p>{props.selectedName ?? "対戦AI未選択"}</p></div><b className={allGreen ? "analysis-ready" : "analysis-blocked"}>{allGreen ? "提出準備完了" : "未完了"}</b></header>

    <section className="analysis-card deck-diff-card">
      <div className="analysis-title"><div><span>Current → Candidate</span><h4>デッキ差分</h4></div><strong>{diff.reduce((sum, item) => sum + Math.abs(item.delta), 0) / 2}枚変更</strong></div>
      {diff.length ? <div className="deck-diff-list">{diff.map((item) => <div key={item.cardId} className={item.delta > 0 ? "diff-add" : "diff-remove"}><b>{item.delta > 0 ? "+" : "−"}</b><span>{item.name}<small>#{item.cardId}</small></span><strong>×{Math.abs(item.delta)}</strong></div>)}</div> : <p className="analysis-empty">Baselineから変更はありません。</p>}
      <button type="button" onClick={props.onPromoteBaseline} disabled={!props.candidateDeck.length || !diff.length}>この候補を新しいCurrentにする</button>
    </section>

    <section className="analysis-card identity-card">
      <div className="analysis-title"><div><span>IDENTITY</span><h4>Bundle識別情報</h4></div></div>
      <dl><div><dt>Current Deck SHA</dt><dd>{short(props.baselineDeckSha)}</dd></div><div><dt>Candidate Deck SHA</dt><dd>{short(props.candidateDeckSha)}</dd></div><div><dt>Policy SHA</dt><dd>{short(props.context?.policySha)}</dd></div><div><dt>Engine SHA</dt><dd>{short(props.context?.engineSha)}</dd></div><div><dt>Freeze SHA</dt><dd>{short(props.context?.freezeSha)}</dd></div><div><dt>Bundle SHA</dt><dd>{short(props.context?.bundleSha)}</dd></div></dl>
    </section>

    <section className="analysis-card synergy-card">
      <div className="analysis-title"><div><span>STATIC + EVIDENCE</span><h4>シナジー警告</h4></div><strong>{warnings.length}</strong></div>
      {warnings.length ? <div className="synergy-list">{warnings.map((item, index) => <article key={`${item.title}-${index}`} className={`synergy-${item.severity}`}><header><b>{item.severity === "danger" ? "⚠" : item.severity === "warning" ? "△" : "i"}</b><strong>{item.title}</strong><span>{item.source === "evaluation" ? "実測" : "静的"}</span></header><p>{item.detail}</p></article>)}</div> : <p className="analysis-empty">検出された静的注意はありません。安全を保証する表示ではありません。</p>}
    </section>

    <section className="analysis-card intent-card">
      <div className="analysis-title"><div><span>DECK INTENT</span><h4>デッキ意図</h4></div></div>
      {props.report?.intent ? <dl><div><dt>勝ち筋</dt><dd>{props.report.intent.winCondition || "未記入"}</dd></div><div><dt>理想ターン</dt><dd>{props.report.intent.idealTurns.length ? props.report.intent.idealTurns.join(" → ") : "未記入"}</dd></div><div><dt>ACE理由</dt><dd>{props.report.intent.aceReason || "未記入"}</dd></div><div><dt>負け筋</dt><dd>{props.report.intent.lossConditions.length ? props.report.intent.lossConditions.join(" / ") : "未記入"}</dd></div><div><dt>不変条件</dt><dd>{props.report.intent.invariants.length ? props.report.intent.invariants.join(" / ") : "未記入"}</dd></div></dl> : <p className="analysis-empty">Deck Intentは未提供です。Agentフォルダーへdeck-analysis.jsonを入れるか、分析JSONを読み込んでください。</p>}
    </section>

    <section className="analysis-card matchup-card">
      <div className="analysis-title"><div><span>MATCHUP EVIDENCE</span><h4>Current / Candidate対面比較</h4></div></div>
      {matchupNames.length ? <div className="matchup-table"><div className="matchup-head"><span>対面</span><b>{current?.name ?? "Current"}</b><b>{candidate?.name ?? "Candidate"}</b></div>{matchupNames.map((name) => {
        const left = current?.matchups.find((item) => item.name === name);
        const right = candidate?.matchups.find((item) => item.name === name);
        const rightRate = right ? matchupRate(right) : null;
        return <div className="matchup-row" key={name}><span>{name}</span><div><strong>{left ? rateText(left.wins, left.losses, left.draws) : "—"}</strong><small>{left ? `${left.wins + left.losses + (left.draws ?? 0)}戦` : "未計測"}</small></div><div><strong>{right ? rateText(right.wins, right.losses, right.draws) : "—"}</strong><small>{right ? `${right.wins + right.losses + (right.draws ?? 0)}戦${rightRate !== null && rightRate >= 0.5 ? "" : ""}` : "未計測"}</small></div></div>;
      })}</div> : <p className="analysis-empty">対面結果は未提供です。勝率を推測表示しません。</p>}
      {props.report?.evaluation && <div className="evaluation-proof"><span>評価ID {props.report.evaluation.evaluationId || "—"}</span><span>{props.report.evaluation.method || "方式未記載"}</span><span>Engine error {props.report.evaluation.engineErrors}</span><span>Timeout {props.report.evaluation.timeouts}</span><span>{props.report.evaluation.evaluatedAt || "日時未記載"}</span></div>}
    </section>

    <section className="analysis-card gate-card">
      <div className="analysis-title"><div><span>BUNDLE GATE</span><h4>提出前チェック</h4></div><strong>{gates.filter((item) => item.status === "pass").length}/{gates.length}</strong></div>
      <div className="analysis-gates">{gates.map((item) => <GateRow key={item.id} item={item} />)}</div>
      <div className={`gate-verdict ${allGreen ? "ready" : "blocked"}`}><strong>{allGreen ? "全条件PASS" : "提出候補へ昇格不可"}</strong><span>{allGreen ? "表示中のHashと評価証跡が一致しています。" : "未確認または不一致の項目を解消してください。"}</span></div>
    </section>

    <section className="analysis-card report-card"><div><strong>分析データ</strong><span>{props.context?.reportSource ?? "自動検出なし"}</span></div><button type="button" onClick={() => reportRef.current?.click()}>分析JSONを読み込む</button><input ref={reportRef} className="file-input" type="file" accept=".json,application/json" onChange={(event) => { void importReport(event.target.files?.[0]); event.currentTarget.value = ""; }} /></section>
  </aside>;
}
