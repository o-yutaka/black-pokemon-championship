# BLACK Pokémon Championship Lab

Isolated two-candidate laboratory for the Kaggle Pokémon TCG AI Battle.

This repository contains **only**:

1. Team Rocket's Mewtwo ex / Team Rocket's Spidops BLACK v1
2. Cynthia's Garchomp ex / Cynthia's Spiritomb BLACK v1

It includes the deck-specific policies, legal-action boundary, official cabt battle adapter, documented Search lifecycle adapter, static gates, materializer, and paired smoke runner.

The official `libcg.so` binary is deliberately not redistributed. WSL2 resolves the local reference engine from `/home/user/HROS/submission/cg` and records its SHA-256. Kaggle `cabt 1.32.0` remains the competition authority; its exact server binary hash is unverified.

## Current verdict

```text
STATIC_CANDIDATE_BUILD = PASS target
ENGINE_ADAPTER         = IMPLEMENTED
OFFICIAL_ENGINE_SMOKE  = LOCAL_REQUIRED
WIN_RATE               = UNVERIFIED
SUBMISSION_PROMOTION   = HOLD
```

## Static gate

```bash
python scripts/run_static_gate.py
python -m pytest -q
```

## Direct official-engine smoke

```bash
python scripts/run_official_smoke.py \
  --cg-dir /home/user/HROS/submission/cg \
  --games 20 \
  --out artifacts/official_smoke_20.json
```

The runner executes:

```text
cg.game.battle_start(deck0, deck1)
→ current.yourIndex dispatch
→ agent selection normalized to list[int]
→ cg.game.battle_select(action)
→ current.result
→ cg.game.battle_finish()
```

It alternates seats, records action traces and exact local engine provenance, and does not claim native seed control.

## Materialize for local HROS

```bash
python scripts/materialize_candidate.py \
  --candidate mewtwo_spidops \
  --output /home/user/HROS/artifacts/championship_candidates/mewtwo_spidops

python scripts/materialize_candidate.py \
  --candidate garchomp_spiritomb \
  --output /home/user/HROS/artifacts/championship_candidates/garchomp_spiritomb
```

See [`docs/OFFICIAL_ENGINE_CONTRACT.md`](docs/OFFICIAL_ENGINE_CONTRACT.md) and [`docs/LOCAL_HROS_GATE.md`](docs/LOCAL_HROS_GATE.md).
