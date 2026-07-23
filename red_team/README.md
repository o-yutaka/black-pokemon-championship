# BLACK Official Red Team

Promotion evidence is accepted only when every opponent directory contains a complete, fixed, executable CABT Bundle:

```text
main.py
deck.csv
submission_contract.py
black_engine/...
cg/...
```

The evaluator uses one official `cg/libcg.so` runtime for the battle and loads both agents from their exact Bundles. It never substitutes `deterministic_fallback`, FLM, or a generic heuristic opponent.

## Required matchups

- Grimmsnarl/Froslass
- Crustle/Cornerstone Ogerpon
- Mega Starmie/Cinderace
- Alakazam/Dunsparce
- Mega Abomasnow/Kyogre
- Rocket Mewtwo mirror

## Evidence levels

- `PROMOTION`: current-head candidate, fixed Bundle hashes, official engine, seat-balanced, runtime counters included.
- `ILLUSTRATIVE`: useful for debugging only; cannot promote or reject the candidate.
- `ORACLE`: research-only and must never be merged into production evidence.

Before a run, replace every `REQUIRED_BEFORE_RUN` hash in `manifest.json` with the actual directory tree SHA-256 printed by the evaluator. A mismatch is a hard failure.
