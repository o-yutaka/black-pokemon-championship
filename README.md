# BLACK Dragapult — Strict External-Engine Agent

A standalone stateful agent built for Kaggle CABT with a fixed Dragapult / Drakloak / Cinderace / Dusclops / Dusknoir / Azelf deck.

The main engineering focus is broader than the game domain: **execute only actions exposed by the external engine, reject invalid output, degrade safely under failure, and build the exact reviewed deployment artifact**.

## What this repository demonstrates

| Engineering concern | Implementation |
|---|---|
| External action contract | Option indexes are validated against the current `select.option` array |
| Stateful policy | Deterministic scoring from current board, hand, resources, effects, and targets |
| Failure containment | Timeout, exception, and invalid policy output use a deterministic legal fallback |
| Observability | Runtime source, selection, warnings, and errors are preserved in a decision overlay |
| Artifact integrity | Exact source/runtime/archive file allow-list and deck validation |
| Hosted-runner compatibility | Raw `exec()` probe without assuming normal `__file__` module context |
| Reproducible packaging | Reviewed source is copied into a canonical submission bundle |
| Honest evaluation | Fast evaluation is labeled crash/speed/regression screening, not promotion proof |

Read the full transferable engineering analysis: [`docs/engineering-case-study.md`](docs/engineering-case-study.md).

## Runtime boundary

```text
Official observation
       |
       v
Policy proposes option indexes
       |
       v
Legal selection validator
       |
       +---- valid and within budget ----> policy result
       |
       +---- invalid / timeout / error ---> deterministic fallback
                                               |
                                               v
                                 RuntimeDecision + audit overlay
```

`black_engine/runtime.py` is the final execution boundary. A strategically sensible action is still rejected when it is not legal under the current engine-provided selection contract.

## Canonical submission tree

```text
main.py
deck.csv
submission_contract.py
black_engine/
cg/                 # copied only when building/running
```

There is exactly one reviewed submission policy. No alternate deck policy, runtime deck switching, candidate router, or generated entrypoint exists in the canonical bundle.

`main.py` and `deck.csv` are copied byte-for-byte into the built submission artifact.

## Verification gates

```bash
python scripts/static_gate.py
python -m pytest -q
python scripts/build_submission.py \
  --cg-dir /home/user/HROS/submission/cg \
  --out artifacts/submission.zip
```

The static gate:

- validates the fixed source and deck contract
- rejects direct `__file__` assumptions and environment-specific absolute paths
- builds and extracts the submission artifact
- runs the extracted entrypoint through isolated raw `exec()`
- verifies the 60-card deck handshake and a normal option-index response

## Fast regression screen

```bash
python scripts/fast_eval.py \
  --cg-dir /home/user/HROS/submission/cg \
  --opponent-deck /path/to/opponent/deck.csv \
  --games 1000 \
  --workers 4
```

Outputs:

```text
summary.json
summary.csv
SUMMARY.md
```

This harness is for crash, speed, and regression screening against the supplied external deck with a legal deterministic baseline policy. It is not presented as official leaderboard evidence or a standalone promotion claim.

## Reviewer path

1. [`black_engine/runtime.py`](black_engine/runtime.py) — legality, timeout, failure, fallback
2. [`submission_contract.py`](submission_contract.py) — exact source and archive contract
3. [`scripts/static_gate.py`](scripts/static_gate.py) — deployment-artifact execution gate
4. [`black_engine/policy.py`](black_engine/policy.py) — deterministic stateful policy
5. [`scripts/build_submission.py`](scripts/build_submission.py) — canonical builder
6. [`scripts/fast_eval.py`](scripts/fast_eval.py) — bounded evaluation screen

## Transfer to business agents

The same control-plane principles are implemented in [`AI-AI`](https://github.com/o-yutaka/AI-AI): engine options become allowed tools, hidden-state discipline becomes an evidence boundary, high-impact operations require human approval, and idempotency prevents duplicate external side effects.

## Claim boundary

This repository demonstrates a strict external-engine integration and reproducible evaluation pipeline. It does not claim that its domain heuristic is a universal planner or that local screening replaces official competition evidence.
