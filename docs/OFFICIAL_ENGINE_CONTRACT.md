# Official cabt Engine Contract

## Authority

- Competition runtime authority: `cabt 1.32.0` on Kaggle.
- The exact Kaggle server binary hash is not exposed and must remain `UNVERIFIED`.
- Local WSL2 uses `/home/user/HROS/submission/cg/libcg.so` as the reference engine.
- A local `libcg.so` result is evidence for that exact hash only; it is not proof that the server binary is byte-identical.

## Official Python battle contract

```python
observation, start_data = cg.game.battle_start(deck0, deck1)
observation = cg.game.battle_select(selected_option_indices)
cg.game.battle_finish()
```

Required rules:

- Each deck is exactly 60 card IDs.
- Every action is `list[int]` containing indices into `observation["select"]["option"]`.
- Respect `minCount`, including legal empty selection when `minCount == 0`.
- `current.yourIndex` identifies the acting player.
- `current.result == -1` means the battle is still active; `0` or `1` is the winner.
- `battle_finish()` must execute even after an exception.

## Official Search lifecycle

Only the documented transition-search lifecycle is permitted:

```text
SearchBegin
SearchStep
SearchRelease
SearchEnd
```

No hidden opponent hand, deck, prize, seed setter, or undocumented API is assumed.
Raw ctypes calls are prohibited unless the exact wrapper and `libcg.so` provenance are verified together.

## Native limitation

`battle_start(deck0, deck1)` exposes no seed parameter. Python-side RNG seeding does not make the native battle deterministic. Alternating seats is required, but paired-seed claims are prohibited.

## Repository policy

`libcg.so` is not committed here. The repository resolves it from:

1. `--cg-dir`
2. `CABT_CG_DIR`
3. `$HROS_ROOT/submission/cg`
4. `/home/user/HROS/submission/cg`

The loader requires `game.py`, `sim.py`, and `libcg.so`, records SHA-256 and size, and fails closed if the contract is missing.

## Local gate

```bash
cd /home/user/black-pokemon-championship
python scripts/run_static_gate.py
python -m pytest -q
python scripts/run_official_smoke.py \
  --cg-dir /home/user/HROS/submission/cg \
  --games 20 \
  --out artifacts/official_smoke_20.json
```

Promotion remains blocked until:

- all games complete;
- runtime errors are zero;
- invalid selections are zero;
- engine provenance is recorded;
- candidate mechanics appear in traces;
- larger matchup evaluation is run locally.
