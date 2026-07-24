# Local Engine UI Connection Contract

確定日: 2026-07-24
対象: `o-yutaka/black-pokemon-championship`

## 結論

Engine操作はGitHub Pagesでは行わない。

公開GitHub PagesはUI確認・説明・配布用とし、実際のEngine操作はアプリ起動後に開くローカル画面から行う。

公開サイト:

- https://o-yutaka.github.io/black-pokemon-championship/?v=21

ローカル画面:

- `http://127.0.0.1:<port>/`

## 役割分離

### GitHub Pages

用途:

- UIデザイン確認
- 日本語表示確認
- 画面構造確認
- 操作説明
- 静的デモ

禁止:

- `libcg.so`の直接操作
- `battle_start` / `battle_select` / `battle_finish`
- Search API操作
- localhost Engine Bridgeへの常時接続
- 実対戦状態の変更

### ローカル起動画面

用途:

- 公式Engine操作
- Replay読込
- `battle_start`
- `battle_select`
- `visualize_data`
- Search API
- Policy候補・score・reason表示
- 特性・Trainer・Energy・Switch・Retreat監査
- Waste detector
- before / after state diff

## 接続構成

```text
Browser UI
    ↓ HTTP / WebSocket
Local Bridge Server
    ↓ Python
cg.game / cg.api / libcg.so
```

標準接続先:

```text
http://127.0.0.1:<port>/
ws://127.0.0.1:<port>/ws
```

## UIコード再利用方針

公開版とローカル版は同じUIコンポーネントを使う。

差分は接続モードだけに限定する。

```text
STATIC_DEMO_MODE
  Engine操作ボタン無効
  サンプルReplayのみ

LOCAL_ENGINE_MODE
  Local Bridgeへ接続
  Engine操作有効
  Replay / Search / Policy Overlay有効
```

新しい別UIを作らず、既存のBLACK Battle Studio UIをローカル配信へ再利用する。

## 日本語固定

起動時・再読み込み後も日本語を固定する。

必須条件:

```text
black.uiLocale = "ja"
<html lang="ja">
```

保存先は永続化する。

例:

```javascript
localStorage.setItem("black.uiLocale", "ja");
document.documentElement.lang = "ja";
```

起動時に保存値を読み、未設定でも`ja`を既定値とする。

## 日本語表示対象

最低限、以下を日本語表示する。

- 未接続
- 接続中
- 接続済み
- 再接続中
- Engine起動失敗
- Engine応答エラー
- Replay読込失敗
- 試合開始
- 試合進行中
- 試合終了
- Search開始
- Search解放
- 選択肢なし
- 不正な選択
- セッション不一致
- 古い画面からの操作拒否

## 接続状態モデル

```text
DISCONNECTED
CONNECTING
CONNECTED
RECONNECTING
ENGINE_ERROR
SESSION_ERROR
BATTLE_ACTIVE
BATTLE_FINISHED
```

UIは内部コードではなく日本語ラベルを表示する。

## セキュリティと公開範囲

Local Bridgeは標準で`127.0.0.1`のみにbindする。

禁止:

- 標準設定で`0.0.0.0`へ公開
- 認証なしでLANへ公開
- GitHub Pagesから任意のlocalhost APIを叩く
- Engine binaryをブラウザへ直接配布
- Replayや非公開データの外部送信

## CORS / Mixed Content注意

GitHub PagesはHTTPS、Local Bridgeは通常HTTPまたはWSになる。

そのため公開ページから直接localhostへ接続すると、以下の問題が起きる可能性がある。

- Mixed Content
- CORS
- Private Network Access制限
- WebSocket接続拒否
- ブラウザごとの差異

よって、実Engine操作はローカル画面からのみ行う。

## Engine操作契約

### Action index

UIからEngineへ送る値は`select.option`配列位置。

`Option.index`はzone-relative metadataであり、actionとして送らない。

### Identity

Pokémon個体は次で追跡する。

```text
(playerIndex, serial)
```

`cardId`だけで同名個体を識別しない。

### Session

各試合に一意な`session_id`を発行する。

全操作は以下を含める。

```json
{
  "session_id": "...",
  "battle_id": "...",
  "step": 123,
  "action": [0]
}
```

古い`step`、異なる`session_id`、終了済み`battle_id`は拒否する。

### Resource cleanup

例外時も必ず呼ぶ。

- `battle_finish()`
- `search_release(search_id)`
- `search_end()`

Bridge停止時もfinally相当で解放する。

## API境界

推奨最小API:

```text
GET  /api/status
POST /api/battle/start
POST /api/battle/select
POST /api/battle/finish
GET  /api/battle/state
GET  /api/battle/visualize
POST /api/replay/load
POST /api/search/begin
POST /api/search/step
POST /api/search/release
POST /api/search/end
WS   /ws
```

UIは`cg.game`や`cg.api`を直接importしない。

## Visualizer接続

ローカル画面では以下を同一stepへ結合する。

- `visualize_data()`
- Observation
- legal options
- selected option
- Policy candidate scores
- Ability / Trainer / Energy / Switch / Retreat分類
- TruthState
- ResourceLedger
- before / after diff
- Waste warning

公開GitHub PagesではサンプルJSONのみを表示する。

## 特性表示との接続

ローカルEngineから`select.type=MAIN`かつ`option.type=ABILITY`を受け取った場合、以下を表示する。

- Ability名
- `cardId`
- `playerIndex`
- `serial`
- effect source
- 使用前後差分
- 使用済み状態
- 進化前に使うべきか
- Trainerや進化を先に選んだ場合の警告

## 二重操作防止

以下を必須とする。

- 選択送信中は操作ボタンをlock
- 同一stepの二重送信拒否
- WebSocket再接続後は最新stateを再取得
- stale UIのaction拒否
- Engine応答受信前の次操作禁止

## エラー表示

Python tracebackや内部例外をそのままUIへ出さない。

UI表示:

```text
Engineとの接続に失敗しました
選択内容が現在の局面と一致しません
試合セッションが更新されました
Replayデータを読み込めませんでした
Search状態を解放できませんでした
```

詳細ログはローカルログへ保存する。

## 起動後の動作

```text
1. Local Bridge起動
2. 使用可能port確定
3. Browserで127.0.0.1画面を開く
4. /api/status確認
5. 日本語locale読込
6. Engine status表示
7. 操作可能状態へ遷移
```

自動でGitHub Pagesを開かない。

## 受入条件

```text
GITHUB_PAGES_ENGINE_CONTROL = DISABLED
LOCAL_UI_ENGINE_CONTROL = ENABLED
LOCAL_BIND = 127.0.0.1
UI_LOCALE_DEFAULT = ja
HTML_LANG = ja
CONNECTION_STATUS_JAPANESE = PASS
ERROR_MESSAGES_JAPANESE = PASS
OPTION_ARRAY_POSITION_CONTRACT = PASS
SESSION_STALE_ACTION_GUARD = PASS
BATTLE_FINISH_ON_ERROR = PASS
SEARCH_RELEASE_ON_ERROR = PASS
```

## 公式参照

- CABT公式トップ: https://matsuoinstitute.github.io/cabt/
- CABT API: https://matsuoinstitute.github.io/cabt/api.html
- CABT Game: https://matsuoinstitute.github.io/cabt/game.html
- CABT Sim: https://matsuoinstitute.github.io/cabt/sim.html
- Kaggle Competition: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle
- Kaggle Code: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/code
- Kaggle Rules: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/rules
- Kaggle Leaderboard: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/leaderboard
- Kaggle Environments: https://github.com/Kaggle/kaggle-environments

## 現在の裁定

```text
PUBLIC_PAGE = UI_DEMO_ONLY
LOCAL_PAGE = ENGINE_CONTROL_SURFACE
SHARED_UI_COMPONENTS = REQUIRED
DIRECT_GITHUB_PAGES_TO_ENGINE = REJECT
LOCAL_BRIDGE = REQUIRED
```
