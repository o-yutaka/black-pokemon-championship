# BLACK Battle Studio

Replay-first, iPhone-ready battle viewer and decision analysis PWA for the Pokémon TCG Kaggle project.

## Scope

- Read-only replay visualization
- Snapshot-first truth model
- Event-driven lightweight animation
- AI decision overlays
- Static demo and local JSON import
- No changes to `submission/`, root `deck.csv`, policy runtime, or official engine binaries

## Commands

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

## Truth contract

Each frame is a complete immutable snapshot. Events are used only for presentation. Card instances are keyed by `playerIndex:serial`; `cardId` is metadata and must never be used as the unique per-match identity. Hidden cards are never inferred.

## Runtime boundary

Replay mode is complete and static. Live CABT streaming remains held until the WSL2 official engine is connected and source snapshots are compared against the normalized output.
