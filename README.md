# BLACK Dragapult Championship Submission

Cleanroom single-deck repository for the Kaggle Pokémon TCG AI Battle.

## Fixed submission

- Scorbunny / Cinderace: 1 / 4
- Dreepy / Drakloak / Dragapult ex: 4 / 4 / 3
- Duskull / Dusclops / Dusknoir: 3 / 2 / 2
- Azelf: 2
- Fire Energy: 6
- Psychic Energy: 7
- Total: 60

This branch contains no Mewtwo, Garchomp, Crustle, or Grimmsnarl production candidate. One submission equals one fixed deck.

## Canonical submission files

```text
main.py
deck.csv
submission_contract.py
black_lab.py
black_engine/
```

The official local `cg/` directory is injected only while staging the package. The builder copies `main.py` and `deck.csv` byte-for-byte and rejects drift.

## Gates

```bash
python scripts/run_static_gate.py
python -m pytest -q
python scripts/build_official_hybrid_submission.py \
  --cg-dir /home/user/HROS/submission/cg \
  --out artifacts/dragapult_submission.zip
```

Performance remains unverified until official-engine smoke is run on the exact commit.
