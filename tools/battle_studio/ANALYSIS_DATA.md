# BLACK Analysis UI Foundation v1

Battle Studioは、Agentフォルダー内の次のファイル名を分析証跡として自動検出します。

- `deck-analysis.json`
- `black-analysis.json`
- `analysis/deck-analysis.json`
- `analysis/black-analysis.json`

契約は `schemas/deck-analysis.schema.json` です。

## 原則

- 勝率、対面期待値、シナジー達成率は分析JSONに実測値がある場合だけ表示します。
- 分析JSONがない場合は「未計測」「未提供」と表示し、画面側で推測しません。
- Deck SHAはカード順に依存しない `card_id,count` の正規形から計算します。
- Policy SHAはAgentフォルダー内の実装系 `.py/.json/.yaml/.yml/.toml` から計算し、`deck.csv`、公式Engine、分析JSONを除外します。
- Bundle SHAとEngine SHAはBridgeが登録した実物を使用します。
- Freeze SHAは分析JSONの `hashes.freezeSha` がある場合だけ表示します。

## 最小例

```json
{
  "schemaVersion": "1.0",
  "intent": {
    "winCondition": "勝ち筋を記載",
    "idealTurns": ["T1 初動", "T2 準備", "T3 攻撃"],
    "aceReason": "ACE SPEC採用理由",
    "lossConditions": ["初動事故"],
    "invariants": ["守るべき構築条件"]
  },
  "current": {
    "name": "Current",
    "deckSha": "64文字のSHA-256",
    "bundleSha": "64文字のSHA-256",
    "matchups": []
  },
  "candidate": {
    "name": "Candidate",
    "deckSha": "64文字のSHA-256",
    "bundleSha": "64文字のSHA-256",
    "matchups": []
  },
  "evaluation": {
    "evaluationId": "評価ID",
    "evaluatedAt": "ISO 8601日時",
    "method": "Kaggle公式形式の評価方法",
    "engineErrors": 0,
    "timeouts": 0,
    "smokePassed": true,
    "submissionFormatPassed": true
  },
  "synergy": [],
  "hashes": {
    "policySha": "64文字のSHA-256",
    "freezeSha": "固定コミットまたはFreeze識別子",
    "engineSha": "64文字のSHA-256"
  }
}
```

## 対面データ

`matchups`の各要素は最低でも`name / wins / losses`を持ちます。

```json
{
  "name": "Crustle",
  "wins": 144,
  "losses": 156,
  "draws": 0,
  "firstGames": 150,
  "secondGames": 150,
  "engineErrors": 0,
  "timeouts": 0,
  "ev": -0.02
}
```

表示上の勝率は `(wins + draws * 0.5) / 全試合` です。`ev`は評価側で定義した値をそのまま表示対象にできるよう保持し、Battle Studio側では意味を再定義しません。

## Bundle Gate

以下が全てPASSになるまで「提出準備完了」にはなりません。

- 60枚
- カード枚数ルール
- たねポケモン
- ACE SPEC上限
- `main.py / deck.csv`
- 公式Engine整合
- Deck / Policy / Freeze / Bundle SHA
- 分析JSONのCandidate Deck SHA一致
- 公式Smoke
- 提出形式

公式対戦を試す操作と、提出候補への昇格判定は分離されています。未計測のCandidateでも対戦検証はできますが、提出準備完了にはなりません。
