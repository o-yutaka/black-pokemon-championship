import { useMemo, useState } from "react";
import { BattleBoard, type MotionMode } from "./BattleBoard";
import type { CardArtCatalog } from "./cardArt";
import { phaseJa } from "./locale";
import type { BattleFrame, BattleReplay, CardInstance, SearchTreeNode } from "./types";

type ViewMode = "battle" | "analysis";
type AnalysisLayer = "decision" | "search" | "policy" | "truth" | "evidence";

const ANALYSIS_LAYERS: Array<{ id: AnalysisLayer; label: string }> = [
  { id: "decision", label: "判断" },
  { id: "search", label: "探索" },
  { id: "policy", label: "方策" },
  { id: "truth", label: "勝ち筋" },
  { id: "evidence", label: "証拠" },
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
  if (!decision) return <Empty>この場面には判断ログがありません。</Empty>;
  const priorities = decision.priority ?? [];
  const scores = Object.entries(decision.scores ?? {}).sort(([left], [right]) => left === "total" ? 1 : right === "total" ? -1 : left.localeCompare(right));
  return (
    <section className="ide-card decision-hero">
      <div className="decision-title">
        <div><span>判断 #{decision.decisionId ?? frame.actionCount}</span><h2>{decision.goal}</h2></div>
        <strong>{decision.chosen}</strong>
      </div>
      <div className="hero-metrics">
        <div><span>確信度</span><strong>{percent(decision.confidence)}</strong></div>
        <div><span>予想勝率</span><strong>{percent(decision.expectedWinRate)}</strong></div>
        <div><span>思考時間</span><strong>{decision.elapsedMs == null ? "—" : `${decision.elapsedMs.toFixed(0)} ms`}</strong></div>
        <div><span>行動側</span><strong>{decision.actor === 0 ? "自分" : "相手"}</strong></div>
      </div>
      {priorities.length > 0 && <div className="priority-block"><h3>優先順位</h3><ol>{priorities.map((item) => <li key={item}>{item}</li>)}</ol></div>}
      {scores.length > 0 && <div className="score-grid ide-score-grid">{scores.map(([key, value]) => <div key={key} className={key === "total" ? "total" : ""}><span>{SCORE_LABELS[key] ?? key}</span><strong>{score(value)}</strong></div>)}</div>}
    </section>
  );
}

function BranchKiller({ frame }: { frame: BattleFrame }) {
  const branches = frame.decision?.rejectedBranches ?? [];
  return (
    <section className="ide-card branch-killer">
      <div className="ide-section-title"><div><span>除外した手</span><h2>選ばなかった理由</h2></div><strong>{branches.length}</strong></div>
      {branches.length === 0 ? <Empty>枝刈り理由はAgentから未提供です。</Empty> : <div className="killed-grid">{branches.map((branch, index) => (
        <article key={`${branch.label}-${index}`} className="killed-branch">
          <header><span>除外</span><strong>{branch.label}</strong></header>
          <dl><div><dt>理由</dt><dd>{branch.reason}</dd></div>{branch.evidence.length > 0 && <div><dt>根拠</dt><dd>{branch.evidence.join(" / ")}</dd></div>}</dl>
          {Object.keys(branch.metrics).length > 0 && <div className="branch-metrics">{Object.entries(branch.metrics).map(([key, value]) => <div key={key}><span>{key}</span><strong>{String(value)}</strong></div>)}</div>}
          {branch.killedBy.length > 0 && <div className="killed-by"><span>判定</span>{branch.killedBy.map((policy) => <b key={policy}>{policy}</b>)}</div>}
        </article>
      ))}</div>}
    </section>
  );
}

function SearchNode({ node, depth = 0 }: { node: SearchTreeNode; depth?: number }) {
  const open = depth === 0 || node.status === "selected" || node.status === "expanded";
  return (
    <details className={`search-node status-${node.status}`} open={open}>
      <summary><span className="tree-indent">{depth > 0 ? "└" : "Root"}</span><strong>{node.label}</strong><span className="node-status">{node.status}</span><b>EV {score(node.ev)}</b></summary>
      <div className="node-detail"><div><span>Visits</span><strong>{node.visits ?? "—"}</strong></div><div><span>Mean</span><strong>{score(node.mean)}</strong></div><div><span>Worst</span><strong>{score(node.worst)}</strong></div><div><span>Best</span><strong>{score(node.best)}</strong></div></div>
      {node.reason && <p className="node-reason">{node.reason}</p>}
      {node.children.length > 0 && <div className="search-children">{node.children.map((child) => <SearchNode key={child.id} node={child} depth={depth + 1} />)}</div>}
    </details>
  );
}

function SearchLayer({ frame }: { frame: BattleFrame }) {
  const tree = frame.decision?.searchTree;
  return <section className="ide-card search-tree-panel"><div className="ide-section-title"><div><span>探索</span><h2>候補の比較</h2></div></div>{tree ? <SearchNode node={tree} /> : <Empty>探索木はAgentから未提供です。</Empty>}</section>;
}

function DecisionTimeline({ replay, frameIndex, onSelectFrame }: { replay: BattleReplay; frameIndex: number; onSelectFrame: (index: number) => void }) {
  const items = useMemo(() => {
    let previousTotal: number | null = null;
    return replay.frames.flatMap((item, index) => {
      const decision = item.decision;
      if (!decision) return [];
      const total = decision.scores?.total ?? null;
      const delta = total != null && previousTotal != null ? total - previousTotal : null;
      if (total != null) previousTotal = total;
      return [{ frame: item, index, decision, total, delta }];
    });
  }, [replay]);
  return (
    <section className="ide-card timeline-panel">
      <div className="ide-section-title"><div><span>履歴</span><h2>判断タイムライン</h2></div><strong>{items.length}</strong></div>
      {items.length === 0 ? <Empty>判断履歴はありません。</Empty> : <div className="decision-timeline">{items.map(({ frame: item, index, decision, total, delta }) => (
        <button key={`${item.frameId}-${index}`} type="button" className={index === frameIndex ? "current" : ""} onClick={() => onSelectFrame(index)}>
          <span>T{item.turn} · A{item.actionCount}</span><strong>{decision.chosen}</strong><small>{decision.goal}</small><b>{delta == null ? (total == null ? "—" : score(total)) : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`}</b>
        </button>
      ))}</div>}
    </section>
  );
}

function ReplayLayer({ frame, previousFrame, onSelectCard, catalog, motionMode }: { frame: BattleFrame; previousFrame: BattleFrame | null; onSelectCard: (card: CardInstance) => void; catalog: CardArtCatalog; motionMode: MotionMode }) {
  return (
    <div className="replay-layer simple-replay-layer">
      <BattleBoard frame={frame} previousFrame={previousFrame} onSelect={onSelectCard} catalog={catalog} motionMode={motionMode} />
      <details className="ide-card replay-facts compact-facts">
        <summary>対戦ログと詳細</summary>
        <dl><div><dt>ターン</dt><dd>{frame.turn}</dd></div><div><dt>行動</dt><dd>{frame.actionCount}</dd></div><div><dt>フェーズ</dt><dd>{phaseJa(frame.phase)}</dd></div><div><dt>行動側</dt><dd>{frame.actingPlayer === 0 ? "自分" : "相手"}</dd></div><div><dt>結果</dt><dd>{frame.result ?? "進行中"}</dd></div></dl>
        <h3>イベント</h3>
        <div className="event-log">{frame.events.length ? frame.events.map((event, index) => <div key={`${event.type}-${index}`}><span>{event.type}</span><p>{event.text}</p></div>) : <Empty>イベントはありません。</Empty>}</div>
      </details>
    </div>
  );
}

function PolicyLayer({ frame }: { frame: BattleFrame }) {
  const decision = frame.decision;
  const trace = decision?.policyTrace ?? [];
  const battle = Object.entries(decision?.policyBattle ?? {}).sort(([, left], [, right]) => right - left);
  return <div className="ide-stack"><section className="ide-card"><div className="ide-section-title"><div><span>方策</span><h2>判定ログ</h2></div></div>{trace.length === 0 ? <Empty>方策単位の判定ログは未提供です。</Empty> : <div className="policy-trace">{trace.map((item) => <article key={item.name} className={`policy-${item.status.toLowerCase()}`}><header><strong>{item.name}</strong><span>{item.status}</span><b>{item.score >= 0 ? "+" : ""}{item.score.toFixed(2)}</b></header><p>{item.reason || "理由未提供"}</p></article>)}</div>}</section><section className="ide-card"><div className="ide-section-title"><div><span>比較</span><h2>方策バトル</h2></div></div>{battle.length === 0 ? <Empty>方策同士の比較スコアは未提供です。</Empty> : <div className="bar-list">{battle.map(([name, value], index) => <div key={name}><span>{name}{index === 0 ? " · Winner" : ""}</span><progress max={Math.max(...battle.map(([, scoreValue]) => scoreValue), 1)} value={value} /><strong>{value.toFixed(2)}</strong></div>)}</div>}</section>{decision?.decisionDiff && <section className="ide-card"><div className="ide-section-title"><div><span>差分</span><h2>判断の変化</h2></div></div><dl className="decision-diff"><div><dt>前</dt><dd>{decision.decisionDiff.previous}</dd></div><div><dt>現在</dt><dd>{decision.decisionDiff.current}</dd></div><div><dt>理由</dt><dd>{decision.decisionDiff.why}</dd></div><div><dt>差</dt><dd>{score(decision.decisionDiff.delta)}</dd></div></dl></section>}</div>;
}

function TruthLayer({ frame }: { frame: BattleFrame }) {
  const decision = frame.decision;
  const route = decision?.route;
  const planner = decision?.prizePlanner;
  const ledger = Object.entries(decision?.truthLedger ?? {});
  const progress = route && route.steps.length ? Math.min(100, (route.currentStep / route.steps.length) * 100) : 0;
  return <div className="ide-stack"><section className="ide-card"><div className="ide-section-title"><div><span>勝ち筋</span><h2>勝利ルート</h2></div></div>{!route ? <Empty>勝利経路は未提供です。</Empty> : <><h3>{route.name}</h3><div className="route-progress"><progress max="100" value={progress} /><strong>{Math.min(route.currentStep, route.steps.length)} / {route.steps.length}</strong></div><ol className="route-steps">{route.steps.map((step, index) => <li key={`${step}-${index}`} className={index < route.currentStep ? "done" : index === route.currentStep ? "current" : ""}>{step}</li>)}</ol></>}</section><section className="ide-card"><div className="ide-section-title"><div><span>サイド</span><h2>サイド計画</h2></div></div>{!planner ? <Empty>サイド計画は未提供です。</Empty> : <><div className="hero-metrics"><div><span>必要攻撃</span><strong>{planner.neededAttacks ?? "—"}</strong></div><div><span>予想攻撃</span><strong>{score(planner.expectedAttacks)}</strong></div><div><span>リスク</span><strong>{percent(planner.risk)}</strong></div></div><ol className="candidate-list">{planner.alternatives.map((candidate) => <li key={candidate.label}><span>{candidate.label}</span><strong>{score(candidate.score)}</strong></li>)}</ol></>}</section><section className="ide-card"><div className="ide-section-title"><div><span>事実</span><h2>Truth Ledger</h2></div></div>{ledger.length === 0 ? <Empty>Truth Ledgerは未提供です。</Empty> : <dl className="ledger-grid">{ledger.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value == null ? "—" : String(value)}</dd></div>)}</dl>}</section></div>;
}

function EvidenceLayer({ frame }: { frame: BattleFrame }) {
  const decision = frame.decision;
  const analysis = decision?.boardAnalysis;
  const heatmap = Object.entries(decision?.heatmap ?? {}).sort(([, left], [, right]) => right - left);
  const belief = Object.entries(decision?.hiddenBelief ?? {}).sort(([, left], [, right]) => right - left);
  const counterfactuals = decision?.counterfactuals ?? [];
  return <div className="ide-stack"><section className="ide-card"><div className="ide-section-title"><div><span>盤面</span><h2>盤面評価</h2></div><strong>{analysis?.total ?? "—"}</strong></div>{!analysis ? <Empty>盤面価値の分解は未提供です。</Empty> : <><div className="bar-list">{Object.entries(analysis.components).map(([name, value]) => <div key={name}><span>{name}</span><progress max={Math.max(...Object.values(analysis.components), 1)} value={value} /><strong>{value.toFixed(2)}</strong></div>)}</div><h3>脅威</h3><div className="bar-list threat-list">{Object.entries(analysis.threatMap).map(([name, value]) => <div key={name}><span>{name}</span><progress max={Math.max(...Object.values(analysis.threatMap), 1)} value={value} /><strong>{value.toFixed(2)}</strong></div>)}</div></>}</section><section className="ide-card"><div className="ide-section-title"><div><span>行動</span><h2>ヒートマップ</h2></div></div>{heatmap.length === 0 ? <Empty>行動ヒートマップは未提供です。</Empty> : <div className="bar-list">{heatmap.map(([name, value]) => <div key={name}><span>{name}</span><progress max={Math.max(...heatmap.map(([, scoreValue]) => scoreValue), 1)} value={value} /><strong>{value.toFixed(2)}</strong></div>)}</div>}</section><section className="ide-card"><div className="ide-section-title"><div><span>別の手</span><h2>反実仮想</h2></div></div>{counterfactuals.length === 0 ? <Empty>反実仮想は未提供です。</Empty> : <div className="counterfactual-grid">{counterfactuals.map((item) => <article key={item.label}><strong>{item.label}</strong><div><span>{percent(item.baselineWinRate)}</span><b>→</b><span>{percent(item.alternativeWinRate)}</span></div><p>{item.reason}</p></article>)}</div>}</section><section className="ide-card"><div className="ide-section-title"><div><span>推定</span><h2>非公開情報の推定</h2></div></div>{belief.length === 0 ? <Empty>非公開情報の推定は未提供です。</Empty> : <div className="bar-list">{belief.map(([name, value]) => <div key={name}><span>{name}</span><progress max="1" value={value} /><strong>{percent(value)}</strong></div>)}</div>}</section><section className="ide-card"><div className="ide-section-title"><div><span>変化</span><h2>根拠</h2></div></div>{(decision?.warnings ?? []).map((warning) => <p className="evidence-warning" key={warning}>{warning}</p>)}<ul className="board-diff">{(decision?.boardDiff ?? []).map((change, index) => <li key={`${change}-${index}`}>{change}</li>)}</ul>{!(decision?.warnings?.length || decision?.boardDiff?.length) && <Empty>追加の根拠はありません。</Empty>}</section></div>;
}

export function DecisionIDE({ replay, frame, previousFrame, frameIndex, onSelectFrame, onSelectCard, catalog, motionMode }: { replay: BattleReplay; frame: BattleFrame; previousFrame: BattleFrame | null; frameIndex: number; onSelectFrame: (index: number) => void; onSelectCard: (card: CardInstance) => void; catalog: CardArtCatalog; motionMode: MotionMode }) {
  const [view, setView] = useState<ViewMode>("battle");
  const [layer, setLayer] = useState<AnalysisLayer>("decision");
  return (
    <section className="decision-ide simple-studio">
      <nav className="view-tabs" aria-label="表示切替">
        <button type="button" className={view === "battle" ? "active" : ""} onClick={() => setView("battle")}>対戦画面</button>
        <button type="button" className={view === "analysis" ? "active" : ""} onClick={() => setView("analysis")}>AI分析</button>
      </nav>
      {view === "battle" ? (
        <div className="layer-content"><ReplayLayer frame={frame} previousFrame={previousFrame} onSelectCard={onSelectCard} catalog={catalog} motionMode={motionMode} /></div>
      ) : (
        <>
          <nav className="layer-tabs analysis-tabs" aria-label="AI分析の種類">{ANALYSIS_LAYERS.map((item) => <button key={item.id} type="button" className={layer === item.id ? "active" : ""} onClick={() => setLayer(item.id)}>{item.label}</button>)}</nav>
          <div className="layer-content">
            {layer === "decision" && <div className="decision-dashboard"><DecisionHeader frame={frame} /><BranchKiller frame={frame} /><DecisionTimeline replay={replay} frameIndex={frameIndex} onSelectFrame={onSelectFrame} /></div>}
            {layer === "search" && <SearchLayer frame={frame} />}
            {layer === "policy" && <PolicyLayer frame={frame} />}
            {layer === "truth" && <TruthLayer frame={frame} />}
            {layer === "evidence" && <EvidenceLayer frame={frame} />}
          </div>
        </>
      )}
    </section>
  );
}
