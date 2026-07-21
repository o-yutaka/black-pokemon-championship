# BLACK Dragapult — Standalone Submission

This branch contains exactly one Kaggle CABT agent: **Dragapult / Drakloak / Cinderace / Dusclops / Dusknoir / Azelf**.

No alternate deck policy, candidate router, runtime deck switching, or generated entrypoint exists here.

## Canonical submission tree

```text
main.py
deck.csv
submission_contract.py
black_engine/
cg/                 # copied only when building/running
```

`main.py` and `deck.csv` are the reviewed source and are copied byte-for-byte into `submission.zip`.

## Gates

```bash
python scripts/static_gate.py
python -m pytest -q
python scripts/build_submission.py --cg-dir /home/user/HROS/submission/cg --out artifacts/submission.zip
```

## Fast evaluation

```bash
python scripts/fast_eval.py \
  --cg-dir /home/user/HROS/submission/cg \
  --opponent-deck /path/to/opponent/deck.csv \
  --games 1000 --workers 4
```

This fast screen uses the external deck with a legal deterministic baseline policy. It is for crash/speed/regression screening, not a promotion claim. Live progress is printed as games finish. Final outputs are `summary.json`, `summary.csv`, and `SUMMARY.md`.
