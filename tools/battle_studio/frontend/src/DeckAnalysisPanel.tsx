import { useMemo, useRef } from "react";
import { buildBundleGate, deckDiff, matchupRate, parseAnalysisReport, staticSynergyWarnings, type AgentAnalysisContext, type AnalysisCatalogCard, type AnalysisReport, type GateItem, type MatchupMetric } from "./deck-analysis";
import { openReplayEvidence, type ReplayChangeCandidate, type ReplayFailureFinding, type ReplayFailureReport } from "./replay-failure";
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
  replayReport: ReplayFailureReport | null;
  replayHistory: ReplayFailureReport[];
  replayCandidates: ReplayChangeCandidate[];
  onSearchCandidate(name: string): void;
  onClearReplayHistory(): void;
  onReport(report: AnalysisReport, source: string): void;
  onReportError?(message: string): void;
  onPromoteBaseline(): void;
};

function short(value?: string | null): string {
  return value ? value.slice(0, 12) : "—";
}

function GateRow({ item }: { item: GateItem }) {
  return <div className={`analysis-gate-row gate-${item.status}`}><span>{item.status === "pass" ? "✓" : item.status === "fail" ? "×" : "…"}</span><strong>{item.label}</strong><small>{item.detail}</small></div>;
}

function MatchupCell({ metric }: { metric?: MatchupMetric }) {
  if (!metric) return <div><strong>—</strong><small>未計測</small></div>;
  const games = metric.wins + metric.losses + (metric.draws ?? 0);
  const rate = matchupRate(metric);
  return <div className="matchup-cell"><strong>{rate === null ? "未計測" : `${(rate * 100).toFixed(1)}%`}</strong><progress max="1" value={rate ?? 0} /><small>{games}戦{games < 50 ? " · 参考値" : ""}</small><small>先 {metric.firstGames ?? "—"} / 後 {metric.secondGames ?? "—"}</small><small>EV {metric.ev == null ? "—" : `${metric.ev >= 0 ? "+" : ""}${metric.ev.toFixed(3)}`}</small></div>;
}

function outcomeJa(report: ReplayFailureReport | null): string {
  if (!report) return "未読込";
  return { loss: "敗北", win: "勝利", unknown: "結果不明", in_progress: "対戦中" }[report.outcome];
}

function confidenceJa(value: ReplayFailureFinding["confidence"]): string {
  return { high: "高", medium: "中", low: "低" }[value];
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
  const lossHistory = props.replayHistory.filter((item) => item.outcome === "loss");
  const findingSummary = useMemo(() => {
    const result = new Map<string, { title: string; evidence: number; replays: Set<string> }>();
    for (const report of lossHistory) for (const finding of report.findings) {
      const current = result.get(finding.code) ?? { title: finding.title, evidence: 0, replays: new Set<string>() };
      current.evidence += Math.max(1, finding.evidence.length);
      current.replays.add(report.replayId);
      result.set(finding.code, current);
    }
    return [...result.entries()].sort(([, left], [, right]) => right.replays.size - left.replays.size || right.evidence - left.evidence);
  }, [lossHistory]);

  const importReport = async (file?: File) => {
    if (!file) return;
    try { props.onReport(parseAnalysisReport(JSON.parse(await file.text())), file.name); }
    catch (error) { props.onReportError?.(error instanceof Error ? error.message : "分析JSONを読み込めませんでした"); }
  };

  return <aside className="deck-analysis-panel" aria-label="BLACKデッキ分析">
    <header className="analysis-head"><div><span>BLACK ANALYSIS</span><h3>デッキ分析</h3><p>{props.selectedName ?? "対戦AI未選択"}</p></div><b className={allGreen ? "analysis-ready" : "analysis-blocked"}>{allGreen ? "提出準備完了" : "未完了"}</b></header>

    <section className="analysis-card deck-diff-card">
      <div className="analysis-title"><div><span>Current → Candidate</span><h4>デッキ差分</h4></div><strong>{diff.reduce((sum, item) => sum + Math.abs(item.delta), 0) / 2}枚変更</strong></div>
      {diff.length ? <div className="deck-diff-list">{diff.map((item) => <div key={item.cardId} className={item.delta > 0 ? "diff-add" : "diff-remove"}><b>{item.delta > 0 ? "+" : "−"}</b><span>{item.name}<small>#{item.cardId}</small></span><strong>×{Math.abs(item.delta)}</strong></div>)}</div> : <p className="analysis-empty">Baselineから変更はありません。</p>}
      <button type="button" onClick={props.onPromoteBaseline} disabled={!props.candidateDeck.length || !diff.length}>この候補を新しいCurrentにする</button>
    </section>

    <section className="analysis-card replay-failure-card">
      <div className="analysis-title"><div><span>OFFICIAL REPLAY EVIDENCE</span><h4>リプレイ敗因抽出</h4></div><strong>{outcomeJa(props.replayReport)}</strong></div>
      {!props.replayReport && <p className="analysis-empty">対戦記録を開くか、公式対戦を最後まで実行してください。</p>}
      {props.replayReport && <div className={`replay-outcome outcome-${props.replayReport.outcome}`}><strong>{props.replayReport.replayId}</strong><span>{props.replayReport.outcomeBasis}</span></div>}
      {props.replayReport?.outcome === "loss" && <div className="failure-finding-list">{props.replayReport.findings.length ? props.replayReport.findings.map((finding) => <article key={finding.code}><header><strong>{finding.title}</strong><span>信頼度 {confidenceJa(finding.confidence)}</span></header><p>{finding.observation}</p><small>{finding.limitation}</small><div className="finding-evidence">{finding.evidence.map((item) => <button type="button" key={`${finding.code}-${item.frameId}`} onClick={() => openReplayEvidence(props.replayReport!.replayId, item.frameId)}><b>T{item.turn} · A{item.actionCount}</b><span>{item.summary}</span><small>{item.facts.join(" / ")}</small></button>)}</div></article>) : <p className="analysis-empty">安全に分類できる敗因シグナルはありませんでした。</p>}</div>}
      {props.replayReport && props.replayReport.outcome !== "loss" && <p className="analysis-empty">敗北が確定したリプレイだけを敗因集計へ入れます。途中・勝利・勝者不明の試合から変更候補は生成しません。</p>}
    </section>

    <section className="analysis-card failure-history-card">
      <div className="analysis-title"><div><span>AGGREGATED LOSSES</span><h4>敗因シグナル集計</h4></div><strong>{lossHistory.length}敗戦</strong></div>
      {findingSummary.length ? <div className="failure-summary-list">{findingSummary.map(([code, item]) => <div key={code}><span>{item.title}<small>{code}</small></span><strong>{item.replays.size}試合</strong><b>{item.evidence}証拠</b></div>)}</div> : <p className="analysis-empty">確定敗戦の証拠履歴はありません。</p>}
      <div className="history-footer"><span>保存 {props.replayHistory.length}/100試合</span><button type="button" onClick={props.onClearReplayHistory} disabled={!props.replayHistory.length}>履歴を消去</button></div>
    </section>

    <section className="analysis-card replay-candidate-card">
      <div className="analysis-title"><div><span>UNVERIFIED HYPOTHESES</span><h4>変更候補</h4></div><strong>{props.replayCandidates.length}</strong></div>
      {props.replayCandidates.length ? <div className="replay-candidate-list">{props.replayCandidates.map((item) => <article key={item.id}><header><div><span>{item.kind === "deck" ? "デッキ候補" : "Policy候補"}</span><strong>{item.title}</strong></div><b>未検証</b></header><p>{item.reason}</p><div className="candidate-proof"><span>{item.replayIds.length}敗戦</span><span>{item.evidenceCount}証拠</span><span>{item.triggerCodes.join(" / ")}</span></div>{item.options.length > 0 && <div className="candidate-options">{item.options.map((option) => <button type="button" key={option.cardId} onClick={() => props.onSearchCandidate(option.name)}><strong>{option.name}</strong><span>現在{option.currentCount}枚 → +1候補</span><small>#{option.cardId}を検索</small></button>)}</div>}{item.kind === "deck" && <p className="candidate-removal">60枚維持には別カードを{item.requiredRemoval}枚減らす必要があります。削るカードは自動決定しません。</p>}<details><summary>検証方法</summary><p>{item.validationPlan}</p></details></article>)}</div> : <p className="analysis-empty">確定敗戦の証拠がないため、変更候補は生成していません。</p>}
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
      {matchupNames.length ? <div className="matchup-table"><div className="matchup-head"><span>対面</span><b>{current?.name ?? "Current"}</b><b>{candidate?.name ?? "Candidate"}</b></div>{matchupNames.map((name) => <div className="matchup-row" key={name}><span>{name}</span><MatchupCell metric={current?.matchups.find((item) => item.name === name)} /><MatchupCell metric={candidate?.matchups.find((item) => item.name === name)} /></div>)}</div> : <p className="analysis-empty">対面結果は未提供です。勝率・EVを推測表示しません。</p>}
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
