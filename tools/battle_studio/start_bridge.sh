#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRONTEND="$ROOT/tools/battle_studio/frontend"
BACKEND="$ROOT/tools/battle_studio/backend"
VENV="${BLACK_BATTLE_STUDIO_VENV:-$ROOT/.venv-battle-studio}"
PORT="${BLACK_BATTLE_STUDIO_PORT:-8000}"
ENABLE_IPHONE=0

for argument in "$@"; do
  case "$argument" in
    --iphone) ENABLE_IPHONE=1 ;;
    --help|-h)
      printf '使い方: bash tools/battle_studio/start_bridge.sh [--iphone]\n'
      printf '  --iphone  WindowsのLANポート転送とFirewallを管理者権限で設定する\n'
      exit 0
      ;;
    *) printf '不明な引数: %s\n' "$argument" >&2; exit 2 ;;
  esac
done

command -v node >/dev/null || { echo 'Node.jsがありません' >&2; exit 1; }
command -v npm >/dev/null || { echo 'npmがありません' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'python3がありません' >&2; exit 1; }

printf '\n[1/4] フロントエンド依存関係を確認\n'
cd "$FRONTEND"
npm install --no-audit --no-fund

printf '\n[2/4] 日本語UIを本番ビルド\n'
npm run build

printf '\n[3/4] Python Bridge環境を確認\n'
if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --disable-pip-version-check -q -r "$BACKEND/requirements-live.txt"

if [[ "$ENABLE_IPHONE" == "1" ]]; then
  command -v powershell.exe >/dev/null || { echo 'powershell.exeが見つかりません' >&2; exit 1; }
  PS_SCRIPT="$(wslpath -w "$ROOT/tools/battle_studio/enable_iphone_bridge.ps1")"
  printf '\n[4/4] iPhone用LAN公開を設定（Windowsの確認画面で「はい」）\n'
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "\$process = Start-Process powershell.exe -Verb RunAs -PassThru -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"$PS_SCRIPT\" -Port $PORT'; exit \$process.ExitCode"
else
  printf '\n[4/4] PCローカル接続を準備\n'
fi

PC_URL="http://127.0.0.1:${PORT}/"
WINDOWS_IP=""
if command -v powershell.exe >/dev/null; then
  WINDOWS_IP="$(powershell.exe -NoProfile -Command "(Get-NetIPConfiguration | Where-Object { \$_.NetAdapter.Status -eq 'Up' -and \$_.IPv4DefaultGateway } | Select-Object -First 1).IPv4Address.IPAddress" 2>/dev/null | tr -d '\r' | head -n 1 || true)"
fi

printf '\n============================================================\n'
printf 'BLACK Battle Studio Bridge 起動\n'
printf 'PC URL     : %s\n' "$PC_URL"
if [[ -n "$WINDOWS_IP" ]]; then
  printf 'iPhone URL : http://%s:%s/\n' "$WINDOWS_IP" "$PORT"
fi
printf '停止        : Ctrl+C\n'
printf '============================================================\n\n'

(
  for _ in $(seq 1 60); do
    if "$VENV/bin/python" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${PORT}/api/health', timeout=1).read()" >/dev/null 2>&1; then
      if command -v powershell.exe >/dev/null; then
        powershell.exe -NoProfile -Command "Start-Process '$PC_URL'" >/dev/null 2>&1 || true
      fi
      exit 0
    fi
    sleep 0.5
  done
  echo 'Bridgeの起動確認に失敗しました' >&2
) &

cd "$BACKEND"
exec "$VENV/bin/python" -m uvicorn live_server:app --host 0.0.0.0 --port "$PORT"
