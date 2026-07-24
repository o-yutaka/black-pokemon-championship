import { useMemo, useState } from "react";
import { BattleBoard } from "./BattleBoard";
import type { BattleFrame, BattleReplay, CardInstance, SearchTreeNode } from "./types";

type Layer = "replay" | "decision" | "search" | "policy" | "truth" | "evidence";

const LAYERS: Array<{ id: Layer; label: string }> = [
  { id: "replay", label: "Replay" },
  { id: "decision", label: "Decision" },
  { id: "search", label: "Search" },
  { id: "policy", label: "Policy" },
  { id: "truth", label: "Truth" },
  { id: "evidence", label: "Evidence" },
];

const SCORE_LABELS: Record<string, string> = {
  policy: "方策",
  ability: "特性",
  prizeRoute: "サイド経路",
  wastePenalty: "無駄ペナルティ",
  lethal: "リーサル",
  total: "合計",
};

function percent(value: number | null | undefined): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function score(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(2);
}

function Empty({ children }: { children: string }) {
  return <p className="ide-empty">{children}</p>;
}

function DecisionHeader({ frame }: { frame: BattleFrame }) {
  const decision = frame.decision;
  if (!decision) return <Empty>このフレームには判断ログがありません。</Empty>;
  const priorities = decision.priority ?? [];
  const scores = Object.entries(decision.scores ?? {}).sort(([left], [right]) => left === "total" ? 1 : right === "total" ? -1 : left.localeCompare(right));
  return <section className="ide-card decision-hero">
    <div className="decision-title"><div><span>Decision #{decision.decisionId ?? frame.actionCount}</span><h2>{decision.goal}</h2></div><strong>{decision.chosen}</strong></div>
    <div className="hero-metrics"><div><span>Confidence</span><strong>{percent(decision.confidence)}</strong></div><div><span>Expected WR</span><strong>{percent(decision.expectedWinRate)}</strong></div><div><span>Think</span><strong>{decision.elapsedMs == null ? "—" : `${decision.elapsedMs.toFixed(0)} ms`}</strong></div><div><span>Actor</span><strong>P{decision.actor + 1}</strong></div></div>
    {priorities.length > 0 && <div className="priority-block"><h3>Priority</h3><ol>{priorities.map((item) => <li key={item}>{item}</li>)}</ol></div>}
    {scores.length > 0 && <div className="score-grid ide-score-grid">{scores.map(([key, value]) => <div key={key} className={key === "total" ? "total" : ""}><span>{SCORE_LABELS[key] ?? key}</span><strong>{score(value)}</strong></div>)}</div>}
  </section>;
}

function BranchKiller({ frame }: { frame: BattleFrame }) {
  const branches = frame.decision?.rejectedBranches ?? [];
  return <section className="ide-card branch-killer"><div className="ide-section-title"><div><span>BLACK独自</span><h2>Branch Killer</h2></div><strong>{branches.length}</strong></div>
    {branches.length === 0 ? <Empty>枝刈り理由はAgentから未提供です。選択結果だけから理由は捏造しません。</Empty> : <div className="killed-grid">{branches.map((branch, index) => <article key={`${branch.label}-${index}`} className="killed-branch">
      <header><span>Rejected</span><strong>{branch.label}</strong></header>
      <dl><div><dt>Reason</dt><dd>{branch.reason}</dd></div>{branch.evidence.length > 0 && <div><dt>Evidence</dt><dd>{branch.evidence.join(" / ")}</dd></div>}</dl>
      {Object.keys(branch.metrics).length > 0 && <div className="branch-metrics">{Object.entries(branch.metrics).map(([key, value]) => <div key={key}><span>{key}</span><strong>{String(value)}</strong></div>)}</div>}
      {branch.killedBy.length > 0 && <div className="killed-by"><span>Killed by</span>{branch.killedBy.map((policy) => <b key={policy}>{policy}</b>)}</div>}
    </article>)}</div>}
  </section>;
}

function SearchNode({ node, depth = 0 }: { node: SearchTreeNode; depth?: number }) {
  const open = depth === 0 || node.status === "selected" || node.status === "expanded";
  return <details className={`search-node status-${node.status}`} open={open}>
    <summary><span className="tree-indent">{depth > 0 ? "└" : "Root"}</span><strong>{node.label}</strong><span className="node-status">{node.status}</span><b>EV {score(node.ev)}</b></summary>
    <div className="node-detail"><div><span>Visits</span><strong>{node.visits ?? "—"}</strong></div><div><span>Mean</span><strong>{score(node.mean)}</strong></div><div><span>Worst</span><strong>{score(node.worst)}</strong></div><div><span>Best</span><strong>{score(node.best)}</strong></div></div>
    {node.reason && <p className="node-reason">{node.reason}</p>}
    {node.children.length > 0 && <div className="search-children">{node.children.map((child) => <SearchNode key={child.id} node={child} depth={depth + 1} />)}</div>}
  </details>;
}

function SearchLayer({ frame }: { frame: BattleFrame }) {
  const tree = frame.decision?.searchTree;
  return <section className="ide-card search-tree-panel"><div className="ide-section-title"><div><span>Layer 3</span><h2>Search Tree</h2></div></div>{tree ? <SearchNode node={tree} /> : <Empty>探索木はAgentから未提供です。公式選択肢だけではVisitsや枝刈り因果は復元できません。</Empty>}</section>;
}

function DecisionTimeline({ replay, frameIndex, onSelectFrame }: { replay: BattleReplay; frameIndex: number; onSelectFrame: (index: number) => void }) {
  const items = useMemo(() => {
    let previousTotal: number | null = null;
    return replay.frames.flatMap((frame, index) => {
      const decision = frame.decision;
      if (!decision) return [];
      const total = decision.scores?.total ?? null;
      const delta = total != null && previousTotal != null ? total - previousTotal : null;
      if (total != null) previousTotal = total;
      return [{ frame, index, decision, total, delta }];
    });
  }, [replay]);
  return <section className="ide-card timeline-panel"><div className="ide-section-title"><div><span>Layer 10</span><h2>Decision Timeline</h2></div><strong>{items.length}</strong></div>
    {items.length === 0 ? <Empty>判断履歴はありません。</Empty> : <div className="decision-timeline">{items.map(({ frame, index, decision, total, delta }) => <button key={`${frame.frameId}-${index}`} type="button" className={index === frameIndex ? "current" : ""} onClick={() => onSelectFrame(index)}>
      <span>T{frame.turn} · A{frame.actionCount}</span><strong>{decision.chosen}</strong><small>{decision.goal}</small><b>{delta == null ? (total == null ? "—" : score(total)) : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`}</b>
    </button>)}</div>}
  </section>;
}

function ReplayLayer({ frame, onSelectCard }: { frame: BattleFrame; onSelectCard: (card: CardInstance) => void }) {
  return <div className="replay-layer"><BattleBoard frame={frame} onSelect={onSelectCard} /><aside className="ide-card replay-facts"><h2>Replay Facts</h2><dl><div><dt>Turn</dt><dd>{frame.turn}</dd></div><div><dt>Action</dt><dd>{frame.actionCount}</dd></div><div><dt>Phase</dt><dd>{frame.phase}</dd></div><div><dt>Acting</dt><dd>P{frame.actingPlayer + 1}</dd></div><div><dt>Result</dt><dd>{frame.result ?? "進行中"}</dd></div></dl><h3>Events</h3><div className="event-log">{frame.events.length ? frame.events.map((event, index) => <div key={`${event.type}-${index}`}><span>{event.type}</span><p>{event.text}</p></div>) : <Empty>イベントはありません。</Empty>}</div></aside></div>;
}

function PolicyLayer({ frame }: { frame: BattleFrame }) {
  const decision = frame.decision;
  const trace = decision?.policyTrace ?? [];
  const battle = Object.entries(decision?.policyBattle ?? {}).sort(([, left], [, right]) => right - left);
  return <div className="ide-stack"><section className="ide-card"><div className="ide-section-title"><div><span>Layer 5</span><h2>Policy Trace</h2></div></div>{trace.length === 0 ? <Empty>Policy単位の判定ログは未提供です。</Empty> : <div className="policy-trace">{trace.map((item) => <article key={item.name} className={`policy-${item.status.toLowerCase()}`}><header><strong>{item.name}</strong><span>{item.status}</span><b>{item.score >= 0 ? "+" : ""}{item.score.toFixed(2)}</b></header><p>{item.reason || "理由未提供"}</p></article>)}</div>}</section>
    <section className="ide-card"><div className="ide-section-title"><div><span>BLACK</span><h2>Policy Battle</h2></div></div>{battle.length === 0 ? <Empty>Policy同士の比較スコアは未提供です。</Empty> : <div className="bar-list">{battle.map(([name, value], index) => <div key={name}><span>{name}{index === 0 ? " · Winner" : ""}</span><progress max={Math.max(...battle.map(([, scoreValue]) => scoreValue), 1)} value={value} /><strong>{value.toFixed(2)}</strong></div>)}</div>}</section>
    {decision?.decisionDiff && <section className="ide-card"><div className="ide-section-title"><div><span>Git型比較</span><h2>Decision Diff</h2></div></div><dl className="decision-diff"><div><dt>Previous</dt><dd>{decision.decisionDiff.previous}</dd></div><div><dt>Current</dt><dd>{decision.decisionDiff.current}</dd></div><div><dt>Why</dt><dd>{decision.decisionDiff.why}</dd></div><div><dt>Delta</dt><dd>{score(decision.decisionDiff.delta)}</dd></div></dl></section>}
  </div>;
}

function TruthLayer({ frame }: { frame: BattleFrame }) {
  const decision = frame.decision;
  const route = decision?.route;
  const planner = decision?.prizePlanner;
  const ledger = Object.entries(decision?.truthLedger ?? {});
  const progress = route && route.steps.length ? Math.min(100, (route.currentStep / route.steps.length) * 100) : 0;
  return <div className="ide-stack"><section className="ide-card"><div className="ide-section-title"><div><span>Layer 7</span><h2>Win Route</h2></div></div>{!route ? <Empty>勝利経路は未提供です。</Empty> : <><h3>{route.name}</h3><div className="route-progress"><progress max="100" value={progress} /><strong>{Math.min(route.currentStep, route.steps.length)} / {route.steps.length}</strong></div><ol className="route-steps">{route.steps.map((step, index) => <li key={`${step}-${index}`} className={index < route.currentStep ? "done" : index === route.currentStep ? "current" : ""}>{step}</li>)}</ol></>}</section>
    <section className="ide-card"><div className="ide-section-title"><div><span>Layer 8</span><h2>Prize Planner</h2></div></div>{!planner ? <Empty>サイド計画は未提供です。</Empty> : <><div className="hero-metrics"><div><span>Needed</span><strong>{planner.neededAttacks ?? "—"}</strong></div><div><span>Expected</span><strong>{score(planner.expectedAttacks)}</strong></div><div><span>Risk</span><strong>{percent(planner.risk)}</strong></div></div><ol className="candidate-list">{planner.alternatives.map((candidate) => <li key={candidate.label}><span>{candidate.label}</span><strong>{score(candidate.score)}</strong></li>)}</ol></>}</section>
    <section className="ide-card"><div className="ide-section-title"><div><span>Layer 6</span><h2>Truth Ledger</h2></div></div>{ledger.length === 0 ? <Empty>Truth Ledgerは未提供です。</Empty> : <dl className="ledger-grid">{ledger.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value == null ? "—" : String(value)}</dd></div>)}</dl>}</section></div>;
}

function EvidenceLayer({ frame }: { frame: BattleFrame }) {
  const decision = frame.decision;
  const analysis = decision?.boardAnalysis;
  const heatmap = Object.entries(decision?.heatmap ?? {}).sort(([, left], [, right]) => right - left);
  const belief = Object.entries(decision?.hiddenBelief ?? {}).sort(([, left], [, right]) => right - left);
  const counterfactuals = decision?.counterfactuals ?? [];
  return <div className="ide-stack"><section className="ide-card"><div className="ide-section-title"><div><span>Layer 6</span><h2>Board Analyzer</h2></div><strong>{analysis?.total ?? "—"}</strong></div>{!analysis ? <Empty>盤面価値の分解は未提供です。</Empty> : <><div className="bar-list">{Object.entries(analysis.components).map(([name, value]) => <div key={name}><span>{name}</span><progress max={Math.max(...Object.values(analysis.components), 1)} value={value} /><strong>{value.toFixed(2)}</strong></div>)}</div><h3>Threat Map</h3><div className="bar-list threat-list">{Object.entries(analysis.threatMap).map(([name, value]) => <div key={name}><span>{name}</span><progress max={Math.max(...Object.values(analysis.threatMap), 1)} value={value} /><strong>{value.toFixed(2)}</strong></div>)}</div></>}</section>
    <section className="ide-card"><div className="ide-section-title"><div><span>Layer 9</span><h2>Heatmap</h2></div></div>{heatmap.length === 0 ? <Empty>行動ヒートマップは未提供です。</Empty> : <div className="bar-list">{heatmap.map(([name, value]) => <div key={name}><span>{name}</span><progress max={Math.max(...heatmap.map(([, scoreValue]) => scoreValue), 1)} value={value} /><strong>{value.toFixed(2)}</strong></div>)}</div>}</section>
    <section className="ide-card"><div className="ide-section-title"><div><span>BLACK</span><h2>Counterfactual</h2></div></div>{counterfactuals.length === 0 ? <Empty>反実仮想は未提供です。</Empty> : <div className="counterfactual-grid">{counterfactuals.map((item) => <article key={item.label}><strong>{item.label}</strong><div><span>{percent(item.baselineWinRate)}</span><b>→</b><span>{percent(item.alternativeWinRate)}</span></div><p>{item.reason}</p></article>)}</div>}</section>
    <section className="ide-card"><div className="ide-section-title"><div><span>Hidden Information</span><h2>Belief</h2></div></div>{belief.length === 0 ? <Empty>Hidden Beliefは未提供です。</Empty> : <div className="bar-list">{belief.map(([name, value]) => <div key={name}><span>{name}</span><progress max="1" value={value} /><strong>{percent(value)}</strong></div>)}</div>}</section>
    <section className="ide-card"><div className="ide-section-title"><div><span>Fact Diff</span><h2>Evidence</h2></div></div>{(decision?.warnings ?? []).map((warning) => <p className="evidence-warning" key={warning}>{warning}</p>)}<ul className="board-diff">{(decision?.boardDiff ?? []).map((change, index) => <li key={`${change}-${index}`}>{change}</li>)}</ul>{!(decision?.warnings?.length || decision?.boardDiff?.length) && <Empty>追加Evidenceはありません。</Empty>}</section></div>;
}

export function DecisionIDE({ replay, frame, frameIndex, onSelectFrame, onSelectCard }: { replay: BattleReplay; frame: BattleFrame; frameIndex: number; onSelectFrame: (index: number) => void; onSelectCard: (card: CardInstance) => void }) {
  const [layer, setLayer] = useState<Layer>("decision");
  return <section className="decision-ide">
    <nav className="layer-tabs" aria-label="Decision IDEレイヤー">{LAYERS.map((item) => <button key={item.id} type="button" className={layer === item.id ? "active" : ""} onClick={() => setLayer(item.id)}>{item.label}</button>)}</nav>
    <div className="layer-content">
      {layer === "replay" && <ReplayLayer frame={frame} onSelectCard={onSelectCard} />}
      {layer === "decision" && <div className="decision-dashboard"><DecisionHeader frame={frame} /><BranchKiller frame={frame} /><DecisionTimeline replay={replay} frameIndex={frameIndex} onSelectFrame={onSelectFrame} /></div>}
      {layer === "search" && <SearchLayer frame={frame} />}
      {layer === "policy" && <PolicyLayer frame={frame} />}
      {layer === "truth" && <TruthLayer frame={frame} />}
      {layer === "evidence" && <EvidenceLayer frame={frame} />}
    </div>
  </section>;
}
