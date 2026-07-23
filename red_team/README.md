# BLACK Official Red Team

Promotion evidence is accepted only when every opponent directory is a complete, fixed, executable CABT Bundle and both agents run on the official `cg/libcg.so` engine.

```text
main.py
deck.csv
profile.json
red_agent.py
submission_contract.py
cg/__init__.py
cg/api.py
cg/game.py
cg/libcg.so
cg/sim.py
cg/utils.py
```

The evaluator never substitutes `deterministic_fallback`, FLM, or `GenericHeuristicPolicy`. The legacy fallback evaluation scripts are intentionally disabled.

## Evidence identity

The opponent policies in this repository are reconstructions. They are not represented as the original competitors' private source code.

- `REPLAY_GROUNDED_RECONSTRUCTION`: exact 60-card official replay deck plus deck-specific action priorities checked against the source replay.
- `REPLAY_AND_FROZEN_BLACK_RECONSTRUCTION`: official replay evidence combined with a frozen BLACK challenger deck.
- `FROZEN_BLACK_CANDIDATE_RECONSTRUCTION`: frozen prior BLACK candidate when the source replay is not mounted.

`audit_red_team_fidelity.py` reports exact-action and attack-action agreement only for sources with a mounted official replay. It never converts reconstruction fidelity into a claimed ladder win rate.

## Matchups

Required promotion core, 200 seat-balanced games each:

- Crustle/Cornerstone Ogerpon
- Cynthia's Garchomp
- Grimmsnarl/Froslass
- Dragapult/Cinderace
- Rocket Mewtwo mirror

Additional diagnostic blocks:

- Mega Starmie/Cinderace
- Alakazam/Dunsparce
- Mega Abomasnow/Kyogre

Total promotion runtime minimum: 1,000 completed games with crash, runtime error, illegal action, mandatory-empty, timeout, fallback, and Search leak all equal to zero.

## Build fixed Bundles

```bash
python scripts/build_red_team_bundles.py \
  --cg-dir /home/user/HROS/submission/cg \
  --lock-out artifacts/red_team_manifest.lock.json
```

This copies the official `cg` files into each generated Bundle and writes exact directory-tree SHA-256 values into the lock manifest. Generated Bundles are research artifacts; source decks, profiles, and evidence identities remain versioned.

## Verify replay fidelity

```bash
python scripts/audit_red_team_fidelity.py \
  --replay-dir /path/to/official-replays
```

Default acceptance for replay-grounded reconstruction is overall action agreement at least 35% and attack agreement at least 95%. This is a reconstruction-quality gate, not matchup promotion evidence.

## Run the official Red Team

```bash
python scripts/run_official_red_team.py \
  --cg-dir /home/user/HROS/submission/cg \
  --candidate-bundle /path/to/extracted-candidate \
  --manifest artifacts/red_team_manifest.lock.json
```

Every matchup alternates candidate seat 0/1. Results include Wilson intervals, seat-specific records, decision timing, Bundle hashes, and separate runtime fault counters.

## Promotion verdict

```bash
python scripts/promotion_gate.py \
  --manifest artifacts/red_team_manifest.lock.json \
  --results artifacts/official_red_team
```

The command returns nonzero and `HOLD` unless every required matchup, seat count, performance threshold, Bundle identity, and runtime condition passes.

## Evidence levels

- `PROMOTION`: current-head candidate, fixed hashes, official engine, seat-balanced, all runtime counters included.
- `ILLUSTRATIVE`: debugging only; cannot promote or reject the candidate.
- `ORACLE`: research-only and never production evidence.
