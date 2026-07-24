# BLACK Decision Overlay v1.1

BLACK Battle Studioのローカル公式Runtimeは、通常のKaggle Agent返り値を壊さずに判断ログを追加取得する。

Decision IDEの画面設計とData honesty ruleは[`DECISION_IDE.md`](./DECISION_IDE.md)を参照。

## 互換動作

通常どおり選択だけを返すAgentは変更不要。

```python
def agent(observation, configuration):
    return [0]
```

この場合、Bridgeが公式`select.option`から以下を自動推定する。

- option index
- action kind
- cardId
- serial
- effectSource
- 公式候補一覧
- Search Treeの外形
- 行動前後の盤面差分

Agent内部のRanker score、Visits、枝刈り理由、Policy因果は存在しないため生成しない。

## 推奨: side-channel hook

Kaggle提出時の返り値はそのままにし、ローカルVisualizerだけ判断情報を取得する。

```python
_LAST_OVERLAY = None


def agent(observation, configuration):
    global _LAST_OVERLAY
    selection = [3]
    _LAST_OVERLAY = {
        "schemaVersion": "1.1",
        "decisionId": "184",
        "goal": "2T Dragapult Attack",
        "priority": ["Energy", "Drakloak", "Candy", "Attack"],
        "confidence": 0.91,
        "expectedWinRate": 0.843,
        "selectedAction": {
            "optionIndex": 3,
            "kind": "ABILITY",
            "cardId": 123,
            "serial": 7,
            "effectSource": "Drakloak"
        },
        "scores": {
            "policy": 42.0,
            "ability": 18.0,
            "prizeRoute": 12.0,
            "wastePenalty": 0.0,
            "total": 72.0
        },
        "candidates": [
            {"label": "Ability", "score": 81.0, "selected": True},
            {"label": "Switch", "score": 14.0, "selected": False, "reason": "RESOURCE_LOOP"}
        ],
        "searchTree": {
            "id": "root",
            "label": "Root",
            "status": "root",
            "ev": 81,
            "visits": 301,
            "mean": 76.4,
            "worst": 44,
            "best": 91,
            "children": [
                {
                    "id": "ability",
                    "label": "Ability",
                    "status": "selected",
                    "ev": 81,
                    "visits": 146,
                    "mean": 82.4,
                    "worst": 61,
                    "best": 89,
                    "children": []
                }
            ]
        },
        "rejectedBranches": [
            {
                "label": "Switch",
                "reason": "RESOURCE_LOOP",
                "evidence": ["Retreat Lost"],
                "metrics": {"Energy Tempo": -12, "Future Attack": "-18%"},
                "killedBy": ["CLOCK_V3", "ENERGY_POLICY"]
            }
        ],
        "policyTrace": [
            {"name": "EnergyPolicy", "status": "PASS", "score": 16, "reason": "Future Damage"}
        ],
        "truthLedger": {
            "Truth": "PASS",
            "Evidence": 5,
            "Engine": "PASS",
            "Seed": 184
        }
    }
    return selection


def get_black_decision_overlay():
    return _LAST_OVERLAY
```

## 取得方式

1. `agent()`がローカル専用の`{"selection": [...], "overlay": {...}}`を返す
2. `get_black_decision_overlay()`
3. `black_decision_overlay()`
4. `BLACK_DECISION_OVERLAY`
5. `last_decision_overlay`

Kaggle提出互換を維持する場合は2番を推奨する。

## Base fields

| Field | 内容 |
|---|---|
| `decisionId` | Decision番号 |
| `goal` | 判断目的 |
| `priority` | 優先順位 |
| `chosen` | 選択行動名 |
| `confidence` | 0〜1 |
| `expectedWinRate` | 0〜1。0〜100入力もBridgeが比率へ正規化 |
| `selectedAction` | optionIndex / kind / cardId / serial / effectSource |
| `scores` | policy / ability / prizeRoute / wastePenalty / total等 |
| `flags` | abilityUsed / lethal / waste等 |
| `warnings` | 判断警告 |
| `candidates` | Ranker候補とscore |
| `alternatives` | 代替候補 |
| `boardDiff` | Agent差分。Bridge自動差分へ追記 |

## Decision IDE fields

| Field | Layer |
|---|---|
| `searchTree` | Search Tree |
| `rejectedBranches` | Branch Killer |
| `policyTrace` | Policy Trace |
| `policyBattle` | Policy Battle |
| `boardAnalysis` | Board Analyzer / Threat Map |
| `route` | Win Route |
| `prizePlanner` | Prize Planner |
| `heatmap` | Heatmap |
| `counterfactuals` | Counterfactual |
| `causalityGraph` | Causality Graph |
| `hiddenBelief` | Hidden Information |
| `decisionDiff` | Decision Diff |
| `truthLedger` | Truth Ledger |

相手Bundleが未対応の場合、相手側は実選択・公式候補・盤面差分まで表示し、内部scoreや理由は表示しない。
