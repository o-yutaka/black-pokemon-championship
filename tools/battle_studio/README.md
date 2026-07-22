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
npm ci
npm run test
npm run build
npm run dev -- --host 0.0.0.0
```

Normalize a CABT replay/export:

```bash
python tools/battle_studio/backend/replay_converter.py input.json output.json
```

## Truth contract

Each frame is a complete immutable snapshot. Events are used only for presentation. Card instances are keyed by `playerIndex:serial`; `cardId` is metadata and must never be used as the unique per-match identity.
