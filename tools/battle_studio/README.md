# BLACK Battle Studio

Pokémon TCG Kaggle向けの、iPhone対応リプレイ表示・デッキ構築・公式エンジン対戦UI。

## 最短起動

WSL2でリポジトリへ移動し、次の1行を実行する。

```bash
bash tools/battle_studio/start_bridge.sh
```

このスクリプトは以下を自動実行する。

- フロントエンド依存関係の確認
- 日本語UIの本番ビルド
- Python仮想環境とBridge依存関係の確認
- `0.0.0.0:8000`でBridge起動
- Windowsブラウザで `http://127.0.0.1:8000/` を自動表示

GitHub Pagesは公開プレビュー用であり、公式エンジン操作時は必ずローカルBridge画面を使う。

## iPhone接続

iPhoneとPCを同じWi-Fiへ接続し、WSL2で次を実行する。

```bash
bash tools/battle_studio/start_bridge.sh --iphone
```

Windowsの管理者確認で「はい」を選ぶと、スクリプトが以下を設定する。

- WSL2の現在IPへWindows TCP 8000を転送
- Windows Defender FirewallのPrivateネットワーク受信許可
- iPhoneで開く `http://PC-IP:8000/` を表示

WSL2再起動後は内部IPが変わる場合があるため、iPhone利用時は毎回`--iphone`で起動する。

## UI言語

UIは日本語固定。初期描画前に次を毎回復元する。

- `localStorage["black.uiLocale"] = "ja"`
- `<html lang="ja" data-ui-locale="ja">`

英語設定や古い保存値が残っていても、日本語へ自動修復する。

## Bridge URL

- Windows PC: `http://127.0.0.1:8000/`
- iPhone: `http://PCのLAN-IP:8000/`
- Bridge自身から開いた場合: 現在の同一オリジン

以前保存された`http://DESKTOP-C3RJG3V:8000/`は、PCでは自動的にloopbackへ移行する。iPhoneではホスト名または保存済みLAN IPを維持する。

## 主な機能

- JSONリプレイ表示
- CABT形状エミュレーター
- FastAPI HTTP/WebSocket Bridge
- 公式Engine ZIPまたはLinux `libcg.so`登録
- 公式ソースZIPのWSL2ローカルC++20ビルド
- Player/Opponent Kaggle Bundle検証
- 隔離した永続Agentプロセス
- `BattleStart → GetBattleData → Agent → Select → VisualizeData`
- 公式盤面・判断・イベントのWebSocket反映
- カード検索式デッキビルダー
- PC/iPhoneドラッグ操作と並べ替え
- 60枚・4枚制限・ACE SPEC・たねポケモン検証
- 公式形式`deck.csv`出力

## 個別開発コマンド

```bash
cd tools/battle_studio/frontend
npm install --no-audit --no-fund
npm test
npm run check
npm run build
```

Bridgeのみ手動起動する場合：

```bash
cd tools/battle_studio/backend
python -m pip install -r requirements-live.txt
python -m uvicorn live_server:app --host 0.0.0.0 --port 8000
```

## 接続スモーク

```bash
cd tools/battle_studio/backend
EXPECT_FRONTEND_DIST=1 python run_connection_smoke.py
```

HTTP health、静的PWA、セッション生成、WebSocket初期盤面、ping/pong、状態遷移、違法選択のfail-closed、切断後の再接続を検証する。

## 保護境界

- `submission/`は変更しない
- ルート`deck.csv`は変更しない
- 公式エンジン・カードデータ本体はGitHubへ公開しない
- 盤面は完全スナップショットを正とし、非公開情報を推測しない
