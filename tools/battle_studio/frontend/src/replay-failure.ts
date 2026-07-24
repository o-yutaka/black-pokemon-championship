import type { BattleFrame, BattleReplay, CardInstance } from "./types";

export const REPLAY_FAILURE_EVENT = "black:replay-failure-analysis";
export const REPLAY_EVIDENCE_FRAME_EVENT = "black:open-replay-evidence";
export const REPLAY_FAILURE_STORAGE_KEY = "black.replayFailureHistory.v1";

export type ReplayOutcome = "loss" | "win" | "unknown" | "in_progress";
export type FailureConfidence = "high" | "medium" | "low";
export type FailureCode =
  | "SETUP_LOW_BOARD"
  | "ENERGY_DEVELOPMENT_MISS"
  | "ATTACK_DELAY"
  | "HAND_STALL"
  | "BENCH_COLLAPSE"
  | "DECK_EXHAUSTION"
  | "PRIZE_RACE_BEHIND"
  | "HIGH_DISCARD_LOAD";

export type ReplayEvidence = {
  frameId: number;
  turn: number;
  actionCount: number;
  summary: string;
  facts: string[];
};

export type ReplayFailureFinding = {
  code: FailureCode;
  title: string;
  confidence: FailureConfidence;
  observation: string;
  limitation: string;
  evidence: ReplayEvidence[];
};

export type ReplayFailureReport = {
  schemaVersion: "1.0";
  replayId: string;
  source: BattleReplay["source"];
  subjectPlayer: 0 | 1;
  winnerPlayer: 0 | 1 | null;
  outcome: ReplayOutcome;
  outcomeBasis: string;
  terminalFrameId: number | null;
  analyzedAt: string;
  findings: ReplayFailureFinding[];
};

export type ReplayCatalogCard = {
  id: number;
  name: string;
  kind: string;
  stage: string;
  rule: string;
  moves: Array<{ name: string; text: string }>;
  basicEnergy: boolean;
  basicPokemon: boolean;
};

export type CandidateCardOption = {
  cardId: number;
  name: string;
  currentCount: number;
  proposedDelta: 1;
};

export type ReplayChangeCandidate = {
  id: string;
  kind: "deck" | "policy";
  status: "unverified";
  title: string;
  triggerCodes: FailureCode[];
  reason: string;
  evidenceCount: number;
  replayIds: string[];
  options: CandidateCardOption[];
  requiredRemoval: number;
  validationPlan: string;
};

function boardCards(frame: BattleFrame, player: 0 | 1): CardInstance[] {
  const state = frame.players[player];
  return [state.active, ...state.bench].filter((card): card is CardInstance => Boolean(card));
}

function energyCount(frame: BattleFrame, player: 0 | 1): number {
  return boardCards(frame, player).reduce((sum, card) => sum + card.energies.length, 0);
}

function attackBy(frame: BattleFrame, player: 0 | 1): boolean {
  const attack = /attack|attacked|ワザ|攻撃/i;
  if (frame.events.some((event) => (event.actor === player || event.actor === null) && attack.test(`${event.type} ${event.text}`))) return true;
  return Boolean(frame.decision?.actor === player && attack.test(`${frame.decision.chosen} ${frame.decision.goal}`));
}

function recoveryBy(frame: BattleFrame, player: 0 | 1): boolean {
  const recovery = /recover|recovery|stretcher|super rod|rescue|回収|つりざお|ストレッチャー|トラッシュ.*手札|トラッシュ.*山札/i;
  return frame.events.some((event) => (event.actor === player || event.actor === null) && recovery.test(`${event.type} ${event.text}`));
}

function explicitWinner(result: string | null): 0 | 1 | null {
  if (!result) return null;
  const value = result.trim().toLowerCase();
  const direct = value.match(/winner\s*[:=]\s*(?:player\s*)?([01])/i) ?? value.match(/(?:winner|勝者)\s*[:=]?\s*p(?:layer)?\s*([12])/i);
  if (direct) {
    const parsed = Number(direct[1]);
    if (/p(?:layer)?/i.test(direct[0]) && parsed >= 1) return (parsed - 1) as 0 | 1;
    return parsed as 0 | 1;
  }
  const pWin = value.match(/\bp([12])\b.*(?:wins?|winner|勝ち|勝利)/i) ?? value.match(/(?:wins?|winner|勝ち|勝利).*\bp([12])\b/i);
  if (pWin) return (Number(pWin[1]) - 1) as 0 | 1;
  const playerWin = value.match(/player\s*([01]).*(?:wins?|winner|勝ち|勝利)/i);
  if (playerWin) return Number(playerWin[1]) as 0 | 1;
  return null;
}

function outcome(replay: BattleReplay, subjectPlayer: 0 | 1): { winner: 0 | 1 | null; state: ReplayOutcome; basis: string; terminal: boolean } {
  const last = replay.frames.at(-1)!;
  const fromText = explicitWinner(last.result);
  if (fromText !== null) return { winner: fromText, state: fromText === subjectPlayer ? "win" : "loss", basis: `result=${last.result}`, terminal: true };
  const zeroPrize = ([0, 1] as const).filter((player) => last.players[player].prizeCount === 0);
  if (zeroPrize.length === 1) {
    const winner = zeroPrize[0];
    return { winner, state: winner === subjectPlayer ? "win" : "loss", basis: `P${winner + 1}のサイドが0枚`, terminal: true };
  }
  if (last.result) return { winner: null, state: "unknown", basis: `結果文字列を安全に解釈できません: ${last.result}`, terminal: true };
  return { winner: null, state: "in_progress", basis: "終局結果が未記録", terminal: false };
}

function evidence(frame: BattleFrame, summary: string, facts: string[]): ReplayEvidence {
  return { frameId: frame.frameId, turn: frame.turn, actionCount: frame.actionCount, summary, facts };
}

function lastOf(frames: BattleFrame[]): BattleFrame {
  return frames.at(-1)!;
}

export function analyzeReplayFailure(replay: BattleReplay, subjectPlayer: 0 | 1 = 0): ReplayFailureReport {
  const resolved = outcome(replay, subjectPlayer);
  const last = replay.frames.at(-1)!;
  const base: ReplayFailureReport = {
    schemaVersion: "1.0",
    replayId: replay.replayId,
    source: replay.source,
    subjectPlayer,
    winnerPlayer: resolved.winner,
    outcome: resolved.state,
    outcomeBasis: resolved.basis,
    terminalFrameId: resolved.terminal ? last.frameId : null,
    analyzedAt: new Date().toISOString(),
    findings: [],
  };
  if (resolved.state !== "loss") return base;

  const findings: ReplayFailureFinding[] = [];
  const early = replay.frames.filter((frame) => frame.turn <= 2);
  const earlyFrames = early.length ? early : replay.frames.slice(0, Math.min(8, replay.frames.length));
  const earlyLast = lastOf(earlyFrames);
  const maxBoard = Math.max(...earlyFrames.map((frame) => boardCards(frame, subjectPlayer).length));
  const maxBench = Math.max(...earlyFrames.map((frame) => frame.players[subjectPlayer].bench.length));
  const maxEnergy = Math.max(...earlyFrames.map((frame) => energyCount(frame, subjectPlayer)));
  const attackFrames = replay.frames.filter((frame) => attackBy(frame, subjectPlayer));
  const firstAttack = attackFrames[0] ?? null;
  const ownActing = replay.frames.filter((frame) => frame.actingPlayer === subjectPlayer);
  const lowHand = ownActing.filter((frame) => frame.players[subjectPlayer].handCount <= 2 && frame.turn <= 4);
  const finalState = last.players[subjectPlayer];
  const opponentState = last.players[subjectPlayer === 0 ? 1 : 0];

  if (maxBoard <= 2 || maxBench === 0) findings.push({
    code: "SETUP_LOW_BOARD",
    title: "序盤の盤面展開が少ない",
    confidence: maxBoard <= 1 ? "high" : "medium",
    observation: `ターン2までの最大盤面は${maxBoard}体、最大ベンチは${maxBench}体でした。`,
    limitation: "盤面が少ないことと敗北の因果は未検証です。先後攻・手札・対面を含む追加集計が必要です。",
    evidence: [evidence(earlyLast, "序盤盤面", [`盤面 ${boardCards(earlyLast, subjectPlayer).length}体`, `ベンチ ${earlyLast.players[subjectPlayer].bench.length}体`, `手札 ${earlyLast.players[subjectPlayer].handCount}枚`])],
  });

  if (maxEnergy === 0) findings.push({
    code: "ENERGY_DEVELOPMENT_MISS",
    title: "序盤のエネルギー展開が観測されない",
    confidence: "high",
    observation: "ターン2まで、場のポケモンについているエネルギーが0枚でした。",
    limitation: "手札内エネルギーや、エネルギー不要の行動は観測できないため、デッキ不足とは断定しません。",
    evidence: [evidence(earlyLast, "エネルギー展開", [`場のエネルギー ${energyCount(earlyLast, subjectPlayer)}枚`, `手札 ${earlyLast.players[subjectPlayer].handCount}枚`])],
  });

  if (!firstAttack || firstAttack.turn > 2) findings.push({
    code: "ATTACK_DELAY",
    title: firstAttack ? "最初の攻撃が遅い" : "攻撃が観測されない",
    confidence: firstAttack ? "medium" : "high",
    observation: firstAttack ? `最初に攻撃を観測したのはターン${firstAttack.turn}でした。` : "リプレイ内で自分側の攻撃イベントを確認できませんでした。",
    limitation: "イベント名・判断ログに攻撃情報が無いリプレイでは過小検出されます。",
    evidence: [evidence(firstAttack ?? last, firstAttack ? "初回攻撃" : "終局まで攻撃なし", firstAttack ? [`ターン ${firstAttack.turn}`, `行動 ${firstAttack.actionCount}`] : [`最終ターン ${last.turn}`, `最終サイド ${finalState.prizeCount}枚`])],
  });

  if (lowHand.length >= 2) {
    const sample = lowHand.slice(-2);
    findings.push({
      code: "HAND_STALL",
      title: "低手札状態が連続",
      confidence: "medium",
      observation: `ターン4までに手札2枚以下の自分行動フレームが${lowHand.length}件ありました。`,
      limitation: "少ない手札が強い盤面や意図的な消費の場合もあるため、ドロー不足とは断定しません。",
      evidence: sample.map((frame) => evidence(frame, "低手札", [`手札 ${frame.players[subjectPlayer].handCount}枚`, `山札 ${frame.players[subjectPlayer].deckCount}枚`, `盤面 ${boardCards(frame, subjectPlayer).length}体`])),
    });
  }

  if (boardCards(last, subjectPlayer).length <= 1 && finalState.bench.length === 0) findings.push({
    code: "BENCH_COLLAPSE",
    title: "終局時に後続盤面がない",
    confidence: "high",
    observation: `終局時の盤面は${boardCards(last, subjectPlayer).length}体、ベンチ0体でした。`,
    limitation: "最終KO直後の一時状態を含む可能性があります。直前フレームと合わせて確認してください。",
    evidence: [evidence(last, "終局盤面", [`バトル場 ${finalState.active ? 1 : 0}体`, "ベンチ 0体", `トラッシュ ${finalState.discard.length}枚`])],
  });

  if (finalState.deckCount <= 2) findings.push({
    code: "DECK_EXHAUSTION",
    title: "山札が枯渇寸前",
    confidence: "high",
    observation: `終局時の山札は${finalState.deckCount}枚でした。`,
    limitation: "山札枚数だけでは過剰ドローか長期戦設計かを判定できません。Policyと対面別clockを確認してください。",
    evidence: [evidence(last, "山札残量", [`山札 ${finalState.deckCount}枚`, `手札 ${finalState.handCount}枚`, `トラッシュ ${finalState.discard.length}枚`])],
  });

  if (finalState.prizeCount >= opponentState.prizeCount + 3) findings.push({
    code: "PRIZE_RACE_BEHIND",
    title: "サイドレースで大きく遅れている",
    confidence: "high",
    observation: `終局時サイドは自分${finalState.prizeCount}枚、相手${opponentState.prizeCount}枚でした。`,
    limitation: "サイド差の原因は攻撃速度・対象選択・盤面崩壊など複数あり、カード変更だけでは解決しない場合があります。",
    evidence: [evidence(last, "サイド差", [`自分 ${finalState.prizeCount}枚`, `相手 ${opponentState.prizeCount}枚`, `差 ${finalState.prizeCount - opponentState.prizeCount}枚`])],
  });

  const recovered = replay.frames.some((frame) => recoveryBy(frame, subjectPlayer));
  if (finalState.discard.length >= 10 && !recovered) findings.push({
    code: "HIGH_DISCARD_LOAD",
    title: "大量トラッシュ後の回収が観測されない",
    confidence: "low",
    observation: `終局時トラッシュは${finalState.discard.length}枚で、回収を示すイベントは検出できませんでした。`,
    limitation: "回収イベントの表記揺れや、回収不要のカード構成があるため低信頼の変更仮説です。",
    evidence: [evidence(last, "トラッシュ負荷", [`トラッシュ ${finalState.discard.length}枚`, `山札 ${finalState.deckCount}枚`, `回収イベント ${recovered ? "あり" : "未検出"}`])],
  });

  return { ...base, findings };
}

export function publishReplayFailureReport(report: ReplayFailureReport): void {
  window.dispatchEvent(new CustomEvent(REPLAY_FAILURE_EVENT, { detail: report }));
}

export function openReplayEvidence(replayId: string, frameId: number): void {
  window.dispatchEvent(new CustomEvent(REPLAY_EVIDENCE_FRAME_EVENT, { detail: { replayId, frameId } }));
}

export function loadReplayFailureHistory(storage: Pick<Storage, "getItem"> = window.localStorage): ReplayFailureReport[] {
  try {
    const raw = storage.getItem(REPLAY_FAILURE_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is ReplayFailureReport => Boolean(item && typeof item === "object" && (item as ReplayFailureReport).schemaVersion === "1.0" && typeof (item as ReplayFailureReport).replayId === "string"));
  } catch { return []; }
}

export function upsertReplayFailureHistory(history: ReplayFailureReport[], report: ReplayFailureReport): ReplayFailureReport[] {
  if (report.outcome === "in_progress") return history;
  return [report, ...history.filter((item) => item.replayId !== report.replayId)].slice(0, 100);
}

export function saveReplayFailureHistory(history: ReplayFailureReport[], storage: Pick<Storage, "setItem"> = window.localStorage): void {
  storage.setItem(REPLAY_FAILURE_STORAGE_KEY, JSON.stringify(history));
}

function cardText(card: ReplayCatalogCard): string {
  return [card.name, card.kind, card.stage, card.rule, ...card.moves.flatMap((move) => [move.name, move.text])].join(" ");
}

function deckCounts(ids: number[]): Map<number, number> {
  const result = new Map<number, number>();
  ids.forEach((id) => result.set(id, (result.get(id) ?? 0) + 1));
  return result;
}

function optionsFor(cards: ReplayCatalogCard[], counts: Map<number, number>, limit = 4): CandidateCardOption[] {
  return cards.filter((card) => card.basicEnergy || (counts.get(card.id) ?? 0) < 4).sort((left, right) => (counts.get(right.id) ?? 0) - (counts.get(left.id) ?? 0) || left.name.localeCompare(right.name)).slice(0, limit).map((card) => ({ cardId: card.id, name: card.name, currentCount: counts.get(card.id) ?? 0, proposedDelta: 1 }));
}

export function generateReplayChangeCandidates(reports: ReplayFailureReport[], deck: number[], catalog: ReplayCatalogCard[]): ReplayChangeCandidate[] {
  const losses = reports.filter((report) => report.outcome === "loss");
  const byCode = new Map<FailureCode, { count: number; replayIds: Set<string> }>();
  for (const report of losses) for (const finding of report.findings) {
    const current = byCode.get(finding.code) ?? { count: 0, replayIds: new Set<string>() };
    current.count += finding.evidence.length || 1;
    current.replayIds.add(report.replayId);
    byCode.set(finding.code, current);
  }
  const counts = deckCounts(deck);
  const inDeck = new Set(deck);
  const existingBasics = catalog.filter((card) => card.basicPokemon && inDeck.has(card.id));
  const existingEnergy = catalog.filter((card) => card.basicEnergy && inDeck.has(card.id));
  const setupSearch = catalog.filter((card) => /buddy-buddy poffin|battle vip pass|nest ball|なかよしポフィン|バトルvipパス|ネストボール|たねポケモン.*ベンチ|山札.*たねポケモン/i.test(cardText(card)));
  const drawSearch = catalog.filter((card) => /professor|博士|iono|ナンジャモ|lillie|リーリエ|draw|山札.*引|手札.*引/i.test(cardText(card)));
  const recovery = catalog.filter((card) => /night stretcher|super rod|rescue|ナイトストレッチャー|すごいつりざお|回収|トラッシュ.*手札|トラッシュ.*山札/i.test(cardText(card)));
  const result: ReplayChangeCandidate[] = [];

  const add = (input: Omit<ReplayChangeCandidate, "status">) => {
    if (!result.some((item) => item.id === input.id)) result.push({ ...input, status: "unverified" });
  };
  const stat = (...codes: FailureCode[]) => {
    const matches = codes.map((code) => byCode.get(code)).filter((item): item is { count: number; replayIds: Set<string> } => Boolean(item));
    return { evidenceCount: matches.reduce((sum, item) => sum + item.count, 0), replayIds: [...new Set(matches.flatMap((item) => [...item.replayIds]))] };
  };

  if (byCode.has("SETUP_LOW_BOARD")) {
    const proof = stat("SETUP_LOW_BOARD");
    add({ id: "setup-basic-plus", kind: "deck", title: "主軸たねポケモン +1を検証", triggerCodes: ["SETUP_LOW_BOARD"], reason: "序盤の最大盤面が少ない敗戦が観測されました。既存の主軸たねを増やした候補Bundleを公式対戦で比較します。", ...proof, options: optionsFor(existingBasics, counts), requiredRemoval: 1, validationPlan: "同一Policy・同一Engineで先後攻を揃え、初動盤面数・攻撃開始ターン・対面別勝率を比較する。" });
    add({ id: "setup-search-plus", kind: "deck", title: "たね展開札 +1を検証", triggerCodes: ["SETUP_LOW_BOARD"], reason: "たね枚数そのものではなく、山札から盤面へ出す経路不足の可能性を分離検証します。", ...proof, options: optionsFor(setupSearch, counts), requiredRemoval: 1, validationPlan: "初手使用率、ターン2盤面数、手札詰まりを公式リプレイから再集計する。" });
  }

  if (byCode.has("ENERGY_DEVELOPMENT_MISS") || byCode.has("ATTACK_DELAY")) {
    const proof = stat("ENERGY_DEVELOPMENT_MISS", "ATTACK_DELAY");
    add({ id: "energy-plus", kind: "deck", title: "既存エネルギー +1を検証", triggerCodes: ["ENERGY_DEVELOPMENT_MISS", "ATTACK_DELAY"], reason: "序盤に場のエネルギーが増えない、または攻撃開始が遅い敗戦が観測されました。エネルギー不足と探索Policyの問題を切り分けます。", ...proof, options: optionsFor(existingEnergy, counts), requiredRemoval: 1, validationPlan: "ターン2までのエネルギー到達率、初回攻撃ターン、不要Attach率を同時比較する。" });
  }

  if (byCode.has("HAND_STALL")) {
    const proof = stat("HAND_STALL");
    add({ id: "draw-plus", kind: "deck", title: "ドロー・手札更新札 +1を検証", triggerCodes: ["HAND_STALL"], reason: "低手札状態が複数フレーム連続した敗戦が観測されました。盤面が完成しているケースを除外して公式評価します。", ...proof, options: optionsFor(drawSearch, counts), requiredRemoval: 1, validationPlan: "ターン4までの平均手札、使用可能行動数、初回攻撃ターン、勝率を比較する。" });
  }

  if (byCode.has("BENCH_COLLAPSE") || byCode.has("HIGH_DISCARD_LOAD")) {
    const proof = stat("BENCH_COLLAPSE", "HIGH_DISCARD_LOAD");
    add({ id: "recovery-plus", kind: "deck", title: "回収・復帰札 +1を検証", triggerCodes: ["BENCH_COLLAPSE", "HIGH_DISCARD_LOAD"], reason: "終局時の後続不足または大量トラッシュが観測されました。回収札が実際に使用可能になるかを確認します。", ...proof, options: optionsFor(recovery, counts), requiredRemoval: 1, validationPlan: "回収対象ありの試合だけを母集団にし、使用率・盤面復帰率・勝率を比較する。" });
  }

  if (byCode.has("DECK_EXHAUSTION")) {
    const proof = stat("DECK_EXHAUSTION");
    add({ id: "draw-stop-policy", kind: "policy", title: "山札保護Policyを検証", triggerCodes: ["DECK_EXHAUSTION"], reason: "終局時に山札2枚以下の敗戦が観測されました。カード追加より先にdraw-stop、optional multi-select、長期戦reserveを確認します。", ...proof, options: [], requiredRemoval: 0, validationPlan: "Policyだけを変更したBundleで、deck-out・必要札到達・対面別勝率を比較する。" });
  }

  if (byCode.has("PRIZE_RACE_BEHIND")) {
    const proof = stat("PRIZE_RACE_BEHIND");
    add({ id: "prize-route-policy", kind: "policy", title: "サイド経路・攻撃対象Policyを検証", triggerCodes: ["PRIZE_RACE_BEHIND"], reason: "終局時のサイド差が大きい敗戦が観測されました。カード変更前に攻撃対象、Boss使用、必要攻撃回数の判断ログを確認します。", ...proof, options: [], requiredRemoval: 0, validationPlan: "同一デッキでPolicyのみ変更し、必要攻撃回数・無駄KO・Boss最終KO率を比較する。" });
  }

  return result.sort((left, right) => right.replayIds.length - left.replayIds.length || right.evidenceCount - left.evidenceCount || left.title.localeCompare(right.title));
}
