# PC Lightweight Simulation

## Purpose

Run repeated BLACK vs opponent matches locally on a PC using the official CABT `cg` engine bindings, while keeping the canonical submission artifact unchanged.

This is an evaluation/research harness, not leaderboard evidence.

## Design goals

- no Docker requirement
- Python standard library only for the harness
- multiprocessing with `spawn`
- one `cg.game` instance per worker
- one BLACK `SubmissionRuntime` per worker
- bounded CPU thread pools for native/math libraries
- no per-game subprocess creation
- JSON summary output
- existing runtime legality and deterministic fallback remain active

## Command

```bash
python scripts/pc_simulate.py \
  --cg-dir /path/to/official/cg \
  --opponent-deck /path/to/opponent.csv \
  --games 10000 \
  --workers 8
```

For the existing HROS layout:

```bash
python scripts/pc_simulate.py \
  --cg-dir /home/user/HROS/submission/cg \
  --opponent-deck /path/to/opponent.csv \
  --games 10000 \
  --workers 8
```

## Output

Default:

```text
artifacts/pc_simulation/summary.json
```

The result contains:

- games
- wins / losses / errors
- win rate
- fallback count
- elapsed time
- games per second
- average steps per decided game
- per-worker results

`official_evidence` is always `false`.

## Why this is faster than the previous screen

The older `fast_eval.py` launches a Python subprocess for every worker. `pc_simulate.py` imports `cg.game` once inside each spawned worker and then runs all assigned games in-process.

The official engine remains the game truth source; only process orchestration is optimized.

## Recommended modes

Quick iteration:

```bash
python scripts/pc_simulate.py --cg-dir /path/to/cg --opponent-deck /path/to/opp.csv --games 1000 --workers 4
```

Heavy local screen:

```bash
python scripts/pc_simulate.py --cg-dir /path/to/cg --opponent-deck /path/to/opp.csv --games 100000 --workers 8
```

## Boundary

```text
BLACK Policy
    |
    v
SubmissionRuntime
    |
    v
Legal Action Gate
    |
    v
Official CABT cg.game
    |
    v
Game result
    |
    v
PC Simulation Summary
```

Do not replace the official engine with a simplified rules simulator in this path. A separate micro-simulator can be added later for heuristic-only benchmarking, but it must never be confused with CABT results.
