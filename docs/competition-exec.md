# Competition execution branch

This branch is derived directly from `main` and is dedicated to executable competition verification.

## Execution path

1. `scripts/static_gate.py` validates the exact submission contract.
2. `pytest` runs the repository regression suite.
3. `scripts/build_submission.py` produces the canonical submission artifact.
4. GitHub Actions stores the resulting artifact for inspection.

The branch deliberately keeps the existing Dragapult policy and submission contract intact. Competition-specific execution infrastructure is additive; it does not silently replace the reviewed policy.

## Local

```bash
python tools/competition_exec.py --cg-dir /path/to/cg
```

The generated report is written to `artifacts/competition_exec.json`.

## CI

Pushing to `competition-exec` automatically runs `.github/workflows/competition-exec.yml`. The workflow is also manually runnable from GitHub Actions.

Kaggle credentials are not committed to the repository. A real hosted submission step should consume credentials only from GitHub/Kaggle secret storage.
