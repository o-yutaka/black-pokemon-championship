export const UI_LOCALE_STORAGE_KEY = "black.uiLocale";
export const DEFAULT_UI_LOCALE = "ja";

type LocaleRoot = {
  lang: string;
  dataset: Record<string, string | undefined>;
};

const EXACT_UI_LABELS: Record<string, string> = {
  Replay: "対戦盤面",
  Decision: "判断",
  Search: "探索",
  Policy: "方策",
  Truth: "真実",
  Evidence: "根拠",
  "Decision IDE": "判断解析",
  "Decision ID": "判断番号",
  Confidence: "確信度",
  "Expected WR": "予想勝率",
  Think: "思考時間",
  Actor: "行動者",
  Priority: "優先順位",
  "Branch Killer": "不採用理由",
  Rejected: "不採用",
  Reason: "理由",
  "Killed by": "判定方策",
  "Search Tree": "探索木",
  Root: "起点",
  Visits: "探索回数",
  Mean: "平均",
  Worst: "最低",
  Best: "最高",
  "Decision Timeline": "判断履歴",
  "Replay Facts": "対戦情報",
  Turn: "ターン",
  Action: "行動数",
  Phase: "段階",
  Acting: "行動者",
  Result: "結果",
  Events: "イベント",
  "Policy Trace": "方策判定",
  "Policy Battle": "方策比較",
  Winner: "首位",
  "Decision Diff": "判断差分",
  Previous: "前回",
  Current: "今回",
  Why: "変更理由",
  Delta: "差分",
  "Win Route": "勝利経路",
  "Prize Planner": "サイド計画",
  Needed: "必要攻撃数",
  Expected: "予想攻撃数",
  Risk: "危険度",
  "Truth Ledger": "真実台帳",
  "Board Analyzer": "盤面評価",
  "Threat Map": "脅威一覧",
  Heatmap: "行動評価",
  Counterfactual: "別の行動なら",
  Counterfactuals: "別の行動なら",
  "Hidden Information": "非公開情報",
  Belief: "推定",
  "Fact Diff": "事実差分",
  Selected: "採用",
  Available: "候補",
  Expanded: "探索済み",
  Pruned: "枝刈り",
  PASS: "合格",
  FAIL: "不合格",
  HOLD: "保留",
  SKIP: "対象外",
  FULL: "すべて",
  BALANCED: "軽量",
  LITE: "最軽量",
  Agent: "対戦AI",
  Engine: "対戦エンジン",
  Bundle: "対戦AI一式",
  "MY DECK": "現在のデッキ",
  "OFFICIAL CARD DATABASE": "公式カード情報",
};

const CATALOG_TERMS: Record<string, string> = {
  Pokemon: "ポケモン",
  Pokémon: "ポケモン",
  Trainer: "トレーナーズ",
  Energy: "エネルギー",
  "Basic Energy": "基本エネルギー",
  "Special Energy": "特殊エネルギー",
  Basic: "たね",
  Stage1: "1進化",
  "Stage 1": "1進化",
  Stage2: "2進化",
  "Stage 2": "2進化",
  Item: "グッズ",
  Supporter: "サポート",
  Stadium: "スタジアム",
  Tool: "ポケモンのどうぐ",
  Ability: "特性",
  Fire: "炎",
  Water: "水",
  Grass: "草",
  Lightning: "雷",
  Psychic: "超",
  Fighting: "闘",
  Darkness: "悪",
  Metal: "鋼",
  Dragon: "ドラゴン",
  Colorless: "無色",
};

function translateText(value: string): string {
  const trimmed = value.trim();
  const exact = EXACT_UI_LABELS[trimmed];
  if (exact) return value.replace(trimmed, exact);
  const decision = trimmed.match(/^Decision\s*#?\s*(.+)$/i);
  if (decision) return value.replace(trimmed, `判断 ${decision[1]}`);
  return value;
}

function translateNode(node: Node): void {
  if (node.nodeType === Node.TEXT_NODE && node.nodeValue) {
    const translated = translateText(node.nodeValue);
    if (translated !== node.nodeValue) node.nodeValue = translated;
    return;
  }
  if (!(node instanceof Element)) return;
  for (const attribute of ["aria-label", "title", "placeholder"]) {
    const value = node.getAttribute(attribute);
    if (value) node.setAttribute(attribute, translateText(value));
  }
  for (const child of node.childNodes) translateNode(child);
}

let observerInstalled = false;

export function initializeJapaneseUi(
  storage: Pick<Storage, "getItem" | "setItem"> = window.localStorage,
  root: LocaleRoot = document.documentElement,
): "ja" {
  const stored = storage.getItem(UI_LOCALE_STORAGE_KEY);
  if (stored !== DEFAULT_UI_LOCALE) storage.setItem(UI_LOCALE_STORAGE_KEY, DEFAULT_UI_LOCALE);
  root.lang = DEFAULT_UI_LOCALE;
  root.dataset.uiLocale = DEFAULT_UI_LOCALE;
  if (!observerInstalled && typeof MutationObserver !== "undefined") {
    observerInstalled = true;
    const observer = new MutationObserver((records) => {
      for (const record of records) {
        if (record.type === "characterData") translateNode(record.target);
        for (const node of record.addedNodes) translateNode(node);
      }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
    window.queueMicrotask(() => translateNode(document.body));
  }
  return DEFAULT_UI_LOCALE;
}

export function liveStatusJa(status: string): string {
  const labels: Record<string, string> = {
    disconnected: "未接続",
    connecting: "接続中",
    connected: "接続済み",
    closed: "切断済み",
    error: "エラー",
    checking: "確認中",
    ready: "接続済み",
    "runner-missing": "接続先確認済み",
    offline: "未接続",
  };
  return labels[status] ?? status;
}

export function phaseJa(value: string): string {
  const labels: Record<string, string> = {
    setup: "対戦準備",
    draw: "山札を引く",
    main: "メイン",
    attack: "ワザ",
    between_turns: "ポケモンチェック",
    end: "ターン終了",
    finished: "対戦終了",
    select: "選択中",
  };
  return labels[value.toLowerCase()] ?? value;
}

export function zoneJa(value: string): string {
  const labels: Record<string, string> = {
    active: "バトル場",
    bench: "ベンチ",
    hand: "手札",
    deck: "山札",
    discard: "トラッシュ",
    prize: "サイド",
    lost: "ロストゾーン",
    stadium: "スタジアム",
  };
  return labels[value.toLowerCase()] ?? value;
}

export function energyJa(value: string): string {
  return CATALOG_TERMS[value] ?? value;
}

export function catalogTermJa(value: string): string {
  if (!value) return value;
  return CATALOG_TERMS[value] ?? value.replace(/Stage\s*1/gi, "1進化").replace(/Stage\s*2/gi, "2進化").replace(/Basic/gi, "たね");
}

export function motionModeJa(value: string): string {
  return ({ full: "すべて", balanced: "軽量", lite: "最軽量" } as Record<string, string>)[value] ?? value;
}
