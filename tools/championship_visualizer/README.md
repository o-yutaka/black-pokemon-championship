# BLACK Championship Replay Visualizer

公式CABTの`visualize_data()`出力、Kaggle Episode JSON、BLACKの分析付きReplayをローカルブラウザで確認する単一HTML Viewer。

## 目的

公式Viewerを置き換えてEngine Truthを再実装するものではない。公式Replayを表示しながら、BLACKのDecision Evidenceを同じFrameで監査する。

表示:

- Active / Bench / HP / Energy / Prize価値
- 手番、手札数、山札数、残りPrize
- `select.option`の合法候補と選択index
- Policy score / runner / search / fallback（Replayに記録されている場合）
- Terminal miss、攻撃不能ex露出、Deck Clock、非永続ダメージ、後続攻撃役不在
- Frame JSON export

## 対応入力

- `visualize_data()`のJSON配列
- `{ "visualize": [...] }`
- `{ "frames": [...] }`
- Kaggle Episodeの`steps[*][*].visualize`
- 各Frameに`obs`と`action`を付加したBLACK Replay

## 起動

```bash
cd tools/championship_visualizer
python3 -m http.server 8765
```

ブラウザで`http://127.0.0.1:8765`を開き、Replay JSONを選択する。外部CDN、外部API、カード画像は使用しない。

## BLACK分析拡張

Frameへ任意で次を追加できる。

```json
{
  "black_analysis": {
    "episode_id": "87655769",
    "runner_id": "PROMOTION_LETHAL_OVERRIDE",
    "verdict": "PASS",
    "decision_ms": 24.7,
    "policy_confidence": 0.96,
    "search_triggered": false,
    "fallback_used": false,
    "terminal_win_available": true,
    "observed_opponent_damage": 360,
    "backup_attacker_ready": true,
    "issues": [],
    "option_scores": {"0": 9999.0, "1": -120.0}
  }
}
```

## 境界

- Viewerは合法手を生成しない。
- ViewerはBattle Stateを変更しない。
- 推測値は`UNVERIFIED`として扱う。
- Engine判定は公式`cg/libcg.so`が最上位Truth。
