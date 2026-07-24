# BLACK Decision Overlay v1

BLACK Battle Studioのローカル公式Runtimeは、通常のKaggle Agent返り値を壊さずに判断ログを追加取得できます。

## 互換動作

通常どおり選択だけを返すAgentは変更不要です。

```python
def agent(observation, configuration):
    return [0]
```

この場合、Bridgeが公式`select.option`から以下を自動推定します。

- 選択したoption index
- action kind
- cardId
- serial
- effectSource
- 公式選択肢一覧
- 行動前後の盤面差分

Agent内部のRanker scoreや理由は存在しないため、画面には「Agentスコア未提供」と表示されます。

## 推奨: side-channel hook

Kaggle提出時の返り値はそのままにし、ローカルVisualizerだけ判断情報を取得します。

```python
_LAST_OVERLAY = None


def agent(observation, configuration):
    global _LAST_OVERLAY
    selection = [3]
    _LAST_OVERLAY = {
        "schemaVersion": "1.0",
        "goal": "prize_route",
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
        "flags": {
            "abilityUsed": True,
            "lethal": False,
            "waste": False
        },
        "warnings": [],
        "candidates": [
            {"label": "Drakloak Ability", "score": 72.0, "selected": True},
            {"label": "Evolve Dragapult", "score": 51.0, "selected": False, "reason": "setup loss"}
        ]
    }
    return selection


def get_black_decision_overlay():
    return _LAST_OVERLAY
```

対応する取得方式は次の順です。

1. `agent()`がローカル専用の`{"selection": [...], "overlay": {...}}`を返す
2. `get_black_decision_overlay()`
3. `black_decision_overlay()`
4. `BLACK_DECISION_OVERLAY`
5. `last_decision_overlay`

Kaggle提出互換を維持する場合は2番を推奨します。

## Overlay fields

| Field | 内容 |
|---|---|
| `goal` | 判断の目的 |
| `chosen` | 選択行動の表示名 |
| `confidence` | 0〜1 |
| `selectedAction` | optionIndex / kind / cardId / serial / effectSource |
| `scores` | policy / ability / prizeRoute / wastePenalty / total等 |
| `flags` | abilityUsed / lethal / waste等 |
| `warnings` | Drakloak未使用、Cinderace保留理由不足等 |
| `candidates` | Ranker候補とscore |
| `alternatives` | 代替行動 |
| `boardDiff` | Agent独自差分。Bridge自動差分へ追記される |

相手Bundleがこの契約に未対応の場合、相手側は実選択と公式盤面差分まで表示され、内部scoreや理由は表示されません。
