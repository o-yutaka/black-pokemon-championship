# BLACK Battle Studio — Decision IDE v1

BLACK Battle Studioはゲーム観戦UIではなく、AIの判断を解析・改善するIDEとして扱う。

```text
Replay
↓
Decision
↓
Search
↓
Policy
↓
Truth
↓
Evidence
```

## Layer 1 — Replay

公式Engineが確定した事実だけを表示する。

- Active / Bench / Hand / Deck / Prize / Discard
- Damage / Energy / Evolution / Trainer
- Battle events

## Layer 2 — Decision

判断の中心画面。

- Decision ID
- Goal
- Priority
- Chosen action
- Confidence
- Expected WR
- Score breakdown
- Decision Timeline

## Layer 3 — Search

探索木を表示する。

- node label
- status: root / available / expanded / selected / pruned
- EV
- Visits
- Mean / Worst / Best
- children

Agentが探索統計を提供しない場合、Bridgeは公式候補一覧から木の外形だけを生成する。この場合Visits / Mean / Worst / Bestは未提供のままとし、推測値を作らない。

## Layer 4 — Branch Killer

枝が切られた理由と、どのPolicyが切ったかを表示する。

```json
{
  "label": "Switch",
  "reason": "RESOURCE_LOOP",
  "evidence": ["Retreat Lost"],
  "metrics": {
    "Energy Tempo": -12,
    "Future Attack": "-18%"
  },
  "killedBy": ["CLOCK_V3", "ENERGY_POLICY", "DRAGAPULT_ROUTE"]
}
```

候補にreasonがある場合のみBridgeがRejectedへ変換する。reasonが無い非選択候補を勝手に枝刈り扱いしない。

## Layer 5 — Policy

- Policy Trace
- PASS / FAIL / HOLD / SKIP
- Policy score
- Reason
- Policy Battle
- Decision Diff

## Layer 6 — Truth / Evidence

- Board Analyzer
- Threat Map
- Win Route
- Prize Planner
- Heatmap
- Counterfactual
- Causality Graph
- Hidden Belief
- Truth Ledger
- Board Diff
- Replay Hash / Seed / Engine / Search status

## Decision Timeline

各frameのdecisionを時系列で並べる。クリックすると同じReplayの対象frameへ移動する。表示スコアはAgentのtotalを使用し、前判断との差分が計算できる場合だけdeltaを表示する。

## Data honesty rule

1. 公式Engineの盤面をTruthとする。
2. Agentが提供した内部値はAgent Evidenceとして表示する。
3. 公式候補から推定できるのは選択肢・選択状態・候補scoreまで。
4. Visits、反実仮想WR、枝刈り理由、Policy因果はAgentが提供しない限り生成しない。
5. 相手Bundleがoverlay未対応なら、相手内部の理由は表示しない。

## Initial implementation priority

1. Branch Killer
2. Search Tree
3. Decision Timeline
4. Policy Trace
5. Route Progress
6. Counterfactual
7. Board Value
8. Prize Planner
9. Heatmap
10. Hidden Belief

Decision IDE v1では1〜3を主要UIとして実装し、4〜10のデータ契約と表示面も同時に用意する。
