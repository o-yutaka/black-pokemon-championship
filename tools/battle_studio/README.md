# BLACK Battle Studio

Replay-first, iPhone-ready battle viewer and decision analysis PWA for the Pokémon TCG Kaggle project.

## Scope

- Read-only replay visualization
- Snapshot-first truth model
- Event-driven lightweight animation
- AI decision overlays
- Static demo and local JSON import
- CABT-shaped deterministic emulator
- FastAPI HTTP/WebSocket live bridge
- Browser Connect Emulator / Live Step / Disconnect controls
- No changes to `submission/`, root `deck.csv`, policy runtime, or official engine binaries

## Replay commands

```bash
cd tools/battle_studio/frontend
npm install --no-audit --no-fund
npm test
npm run build
npm run dev -- --host 0.0.0.0
```

Normalize a recorded CABT snapshot stream:

```bash
python tools/battle_studio/backend/replay_converter.py input.json output.json
```

The converter accepts a top-level frame array or an object containing `frames`, `snapshots`, or `records`. Unsupported shapes fail closed instead of inventing state.

## Live emulator bridge

Build the PWA, install the bridge dependencies, then start the same-origin server:

```bash
cd tools/battle_studio/frontend
npm install --no-audit --no-fund
npm run build
cd ../backend
python -m pip install -r requirements-live.txt
python -m uvicorn live_server:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`, choose **Connect Emulator**, then use **Live Step**. The bridge serves the built PWA and sends authoritative frames over `/ws/battle/{sessionId}`.

Run the real TCP/WebSocket connection smoke:

```bash
cd tools/battle_studio/backend
EXPECT_FRONTEND_DIST=1 python run_connection_smoke.py
```

The smoke verifies HTTP health, static PWA serving, session creation, initial WebSocket snapshot, ping/pong, three state transitions, stable `playerIndex:serial`, fail-closed illegal selection handling, clean close, and reconnection to the latest snapshot.

## Truth contract

Each frame is a complete immutable snapshot. Events are used only for presentation. Card instances are keyed by `playerIndex:serial`; `cardId` is metadata and must never be used as the unique per-match identity. Hidden cards are never inferred.

## Runtime boundary

The CABT-shaped emulator connection is fully exercised in CI. The native `libcg.so` adapter still requires WSL2 because the official engine binary is not redistributed in GitHub. The same HTTP/WebSocket transport is retained for that adapter; native promotion requires a real `BattleStart → VisualizeData → BattleSelect → VisualizeData` smoke on the user's WSL2 engine files.
