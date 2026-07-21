# Local HROS Gate

GitHub static checks cannot prove official `libcg.so` behavior or win rate. Local execution is the next truth layer.

## 1. Clone and static validation

```bash
cd /home/user
git clone https://github.com/o-yutaka/black-pokemon-championship.git
cd black-pokemon-championship
python scripts/run_static_gate.py
python -m pytest -q
```

## 2. Materialize both candidates

```bash
python scripts/materialize_candidate.py --candidate mewtwo_spidops \
  --output /home/user/HROS/artifacts/championship_candidates/mewtwo_spidops --force
python scripts/materialize_candidate.py --candidate garchomp_spiritomb \
  --output /home/user/HROS/artifacts/championship_candidates/garchomp_spiritomb --force
```

Each output contains a self-contained local `main.py`, `deck.csv`, shared policy contracts, and both candidate packages.

## 3. Required official-engine capture

Before performance testing, capture and bind:

- exact attack option IDs/names for Mewtwo, Garchomp, Spiritomb, Spidops, Articuno and Wobbuffet;
- Mewtwo Erasure Ball 0..2 Energy discard select context;
- Spidops Charging Up target/select context;
- Garchomp damage and energy-discard transition;
- Spiritomb damage-counter representation;
- Roserade stacking behavior;
- optional selection (`minCount=0`) behavior.

## 4. Smoke gate

Run each candidate for 10 games first. Require:

```text
completed=10
runtime_errors=0
illegal_actions=0
invalid_selection=0
required_empty_fallback=0
```

Do not interpret win rate at this stage.

## 5. Paired comparison

After contract capture:

- direct Mewtwo vs Garchomp: 100 paired games, seat 50/50;
- each candidate vs Crustle, Grimmsnarl, Dragapult and Alakazam: 100 paired games each;
- preserve identical engine budget and seeds;
- record first decisive error and candidate failure bucket.

## Promotion rule

No candidate becomes submission-ready without:

1. official smoke PASS;
2. exact option contract binding;
3. no illegal/runtime regression;
4. paired performance evidence;
5. independent deck-count/fingerprint verification.
