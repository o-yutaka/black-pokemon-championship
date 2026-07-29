#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRONTEND="$ROOT/tools/battle_studio/frontend"
BACKEND="$ROOT/tools/battle_studio/backend"
VENV="${BLACK_BATTLE_STUDIO_VENV:-$ROOT/.venv-battle-studio}"
PORT="${BLACK_BATTLE_STUDIO_PORT:-8000}"
ENABLE_IPHONE=0
ENABLE_SIMULATOR=0

for argument in "$@"; do
  case "$argument" in
    --iphone) ENABLE_IPHONE=1 ;;
    --simulator) ENABLE_SIMULATOR=1 ;;
    --help|-h)
      printf '使い方: bash tools/battle_studio/start_bridge.sh [--iphone] [--simulator]\n'
      printf '  --iphone     WindowsのLANポート転送とFirewallを管理者権限で設定する\n'
      printf '  --simulator  公式セッション限定の全カード表示切替を許可する（初期値OFF）\n'
      printf '  カードDBを手動指定する場合: BLACK_CARD_DATA_DIR=/path/to/data bash tools/battle_studio/start_bridge.sh\n'
      printf '  別ポートの場合: BLACK_BATTLE_STUDIO_PORT=8010 bash tools/battle_studio/start_bridge.sh\n'
      exit 0
      ;;
    *) printf '不明な引数: %s\n' "$argument" >&2; exit 2 ;;
  esac
done

command -v node >/dev/null || { echo 'Node.jsがありません' >&2; exit 1; }
command -v npm >/dev/null || { echo 'npmがありません' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'python3がありません' >&2; exit 1; }
command -v git >/dev/null || { echo 'gitがありません' >&2; exit 1; }
command -v sha256sum >/dev/null || { echo 'sha256sumがありません' >&2; exit 1; }

# Never mistake an older Bridge on the same port for this launch.
HEALTH_TMP="$(mktemp)"
trap 'rm -f "$HEALTH_TMP"' EXIT
if python3 - "$PORT" >"$HEALTH_TMP" 2>/dev/null <<'PY'
import sys
import urllib.request

port = int(sys.argv[1])
with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
    sys.stdout.buffer.write(response.read())
PY
then
  python3 - "$HEALTH_TMP" <<'PY' >&2 || true
import json, sys
try:
    value = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    print("既存BridgeのhealthはJSONとして読めません")
else:
    runtime = value.get("runtime") or {}
    git = runtime.get("git") or {}
    build = runtime.get("frontendBuild") or {}
    print("エラー: このportでは既にBridgeが応答しています。新しいbuildへ接続したふりをせず停止します。")
    print(f"既存PID: {runtime.get('pid', value.get('pid', 'unknown'))}")
    print(f"既存CWD: {runtime.get('cwd', 'unknown')}")
    print(f"既存source: {git.get('branch', 'unknown')} @ {git.get('head', 'unknown')}")
    print(f"既存build: {build.get('gitBranch', 'unknown')} @ {build.get('gitHead', 'unknown')}")
PY
  printf '既存プロセスを停止するか、BLACK_BATTLE_STUDIO_PORTで別ポートを指定してください。\n' >&2
  exit 3
fi
if command -v ss >/dev/null && ss -ltn "sport = :$PORT" 2>/dev/null | grep -q LISTEN; then
  printf 'エラー: port %s は別プロセスが使用中です。自動killせず停止します。\n' "$PORT" >&2
  ss -ltnp "sport = :$PORT" 2>/dev/null >&2 || true
  exit 3
fi

if [[ "$ENABLE_SIMULATOR" == "1" ]]; then
  export BLACK_ALLOW_SIMULATOR_VIEW=1
else
  unset BLACK_ALLOW_SIMULATOR_VIEW 2>/dev/null || true
fi

GIT_HEAD="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || true)"
GIT_BRANCH="$(git -C "$ROOT" branch --show-current 2>/dev/null || true)"
DIRTY_OUTPUT="$(git -C "$ROOT" status --porcelain=v1 --untracked-files=all 2>/dev/null || true)"
GIT_DIRTY=0
DIRTY_COUNT=0
if [[ -n "$DIRTY_OUTPUT" ]]; then
  GIT_DIRTY=1
  DIRTY_COUNT="$(printf '%s\n' "$DIRTY_OUTPUT" | wc -l | tr -d ' ')"
fi
GIT_FINGERPRINT="$(printf '%s\n%s\n' "$GIT_HEAD" "$DIRTY_OUTPUT" | sha256sum | awk '{print $1}')"
export BLACK_FRONTEND_BUILD_HEAD="$GIT_HEAD"
export BLACK_FRONTEND_BUILD_BRANCH="$GIT_BRANCH"
export BLACK_FRONTEND_BUILD_DIRTY="$GIT_DIRTY"
export BLACK_FRONTEND_BUILD_FINGERPRINT="$GIT_FINGERPRINT"
export BLACK_FRONTEND_BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

printf '\nSOURCE branch=%s head=%s dirty=%s entries=%s fingerprint=%s\n' "${GIT_BRANCH:-detached}" "${GIT_HEAD:-unknown}" "$GIT_DIRTY" "$DIRTY_COUNT" "$GIT_FINGERPRINT"

printf '\n[1/5] フロントエンド依存関係を確認\n'
cd "$FRONTEND"
npm install --no-audit --no-fund

printf '\n[2/5] 日本語UIを本番ビルド\n'
npm run build

printf '\n[3/5] Python Bridge環境を確認\n'
if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --disable-pip-version-check -q -r "$BACKEND/requirements-live.txt"

printf '\n[4/5] 公式カードDBを探索\n'
mapfile -t CARD_DATA_RESULT < <(
  "$VENV/bin/python" - "$BACKEND" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from card_catalog import discover_card_files

try:
    card_path, id_path = discover_card_files()
except (FileNotFoundError, OSError, ValueError) as exc:
    print("MISSING")
    print(str(exc))
else:
    print("FOUND")
    print(str(card_path.parent))
    print(str(card_path))
    print(str(id_path))
PY
)
CARD_DATA_STATUS="${CARD_DATA_RESULT[0]:-MISSING}"
CARD_DATA_SUMMARY="未検出"
if [[ "$CARD_DATA_STATUS" == "FOUND" ]]; then
  export BLACK_CARD_DATA_DIR="${CARD_DATA_RESULT[1]}"
  CARD_DATA_SUMMARY="${CARD_DATA_RESULT[2]} + ${CARD_DATA_RESULT[3]}"
  printf 'カードDB検出: %s\n' "${CARD_DATA_RESULT[2]}"
  printf 'ID一覧検出  : %s\n' "${CARD_DATA_RESULT[3]}"
else
  printf '警告: %s\n' "${CARD_DATA_RESULT[1]:-カードDBが見つかりません}" >&2
  printf 'Bridgeは起動できますが、カード検索はCSV配置まで使用できません。\n' >&2
fi

if [[ "$ENABLE_IPHONE" == "1" ]]; then
  command -v powershell.exe >/dev/null || { echo 'powershell.exeが見つかりません' >&2; exit 1; }
  PS_SCRIPT="$(wslpath -w "$ROOT/tools/battle_studio/enable_iphone_bridge.ps1")"
  printf '\n[5/5] iPhone用LAN公開を設定（Windowsの確認画面で「はい」）\n'
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "\$process = Start-Process powershell.exe -Verb RunAs -PassThru -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"$PS_SCRIPT\" -Port $PORT'; exit \$process.ExitCode"
else
  printf '\n[5/5] PCローカル接続を準備\n'
fi

PC_URL="http://127.0.0.1:${PORT}/"
WINDOWS_IP=""
if command -v powershell.exe >/dev/null; then
  WINDOWS_IP="$(powershell.exe -NoProfile -Command "(Get-NetIPConfiguration | Where-Object { \$_.NetAdapter.Status -eq 'Up' -and \$_.IPv4DefaultGateway } | Select-Object -First 1).IPv4Address.IPAddress" 2>/dev/null | tr -d '\r' | head -n 1 || true)"
fi

SIMULATOR_SUMMARY="無効"
if [[ "$ENABLE_SIMULATOR" == "1" ]]; then
  SIMULATOR_SUMMARY="許可（公式セッション時のみ・初期値OFF）"
fi

printf '\n============================================================\n'
printf 'BLACK Battle Studio Bridge 起動\n'
printf 'PC URL       : %s\n' "$PC_URL"
if [[ -n "$WINDOWS_IP" ]]; then
  printf 'iPhone URL   : http://%s:%s/\n' "$WINDOWS_IP" "$PORT"
fi
printf 'source        : %s @ %s dirty=%s\n' "${GIT_BRANCH:-detached}" "${GIT_HEAD:0:12}" "$GIT_DIRTY"
printf 'build time    : %s\n' "$BLACK_FRONTEND_BUILT_AT"
printf 'build指紋     : %s\n' "$GIT_FINGERPRINT"
printf 'カードDB      : %s\n' "$CARD_DATA_SUMMARY"
printf '全カード表示  : %s\n' "$SIMULATOR_SUMMARY"
printf '公式Runtime   : 起動後 /api/health の capabilities を確認\n'
printf '停止          : Ctrl+C\n'
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
exec "$VENV/bin/python" -m uvicorn main:app --host 0.0.0.0 --port "$PORT"
