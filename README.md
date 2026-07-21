# BLACK Pokémon Championship Lab

Isolated two-candidate laboratory for the Kaggle Pokémon TCG AI Battle.

This repository contains **only**:

1. Team Rocket's Mewtwo ex / Team Rocket's Spidops BLACK v1
2. Cynthia's Garchomp ex / Cynthia's Spiritomb BLACK v1

The repository deliberately excludes the live HROS runtime, official `libcg.so`, online learning, and submission promotion. GitHub proves static contracts; WSL2/HROS supplies official-engine evidence.

## Current verdict

```text
STATIC_CANDIDATE_BUILD = PASS target
OFFICIAL_ENGINE_SMOKE  = LOCAL_REQUIRED
WIN_RATE               = UNVERIFIED
SUBMISSION_PROMOTION   = HOLD
```

## Static gate

```bash
python scripts/run_static_gate.py
python -m pytest -q
```

## Materialize for local HROS

```bash
python scripts/materialize_candidate.py \
  --candidate mewtwo_spidops \
  --output /home/user/HROS/artifacts/championship_candidates/mewtwo_spidops

python scripts/materialize_candidate.py \
  --candidate garchomp_spiritomb \
  --output /home/user/HROS/artifacts/championship_candidates/garchomp_spiritomb
```

Then point the HROS local tournament runner at each generated `main.py` and `deck.csv`.

See [`docs/LOCAL_HROS_GATE.md`](docs/LOCAL_HROS_GATE.md).
