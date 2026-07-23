# BLACK Official Red Team

Promotion evidence is accepted only when every opponent directory is a complete fixed CABT Bundle, the candidate/opponents use the same exact official `cg/libcg.so`, and all identities are frozen in one lock manifest.

## Evidence classes

- `PROMOTION`: a frozen executable BLACK challenger Bundle accepted as strength evidence.
- `STRESS_ONLY`: a replay-grounded reconstruction useful for regression and failure discovery, but not accepted as leaderboard-strength proof.

The policies reconstructed from official replays are not the original competitors' private source code. Replay action fidelity is reconstruction agreement, not opponent strength.

## Required five-matchup pool

Each block is exactly 200 games, candidate seat 0/1 exactly 100 times:

- Crustle / Cornerstone Ogerpon
- Cynthia's Garchomp
- Grimmsnarl / Froslass
- Dragapult / Cinderace
- Rocket Mewtwo mirror

Current strength status:

- `Cynthia's Garchomp`: `STRESS_ONLY`
- `Dragapult / Cinderace`: `PROMOTION` — frozen standalone commit `51a98e353abf257e91c3dccbd14a188baddf73f6`
- `Crustle / Ogerpon`: `STRESS_ONLY`
- `Grimmsnarl / Froslass`: `STRESS_ONLY`
- `Mewtwo mirror`: `PROMOTION` — frozen standalone commit `db4eb14b881e96b3f9b2599ea4c9a5e31c1dbc20`

The builder now has two fail-closed paths. Dragapult and the alternate Rocket Mewtwo mirror are rebuilt from their exact historical submission commits using each commit's own `scripts/build_submission.py`; the same official `cg/libcg.so` is injected and the rebuilt deck must exactly match the locked Red Team deck. Crustle, Garchomp and Grimmsnarl still use replay-grounded reconstruction and remain `STRESS_ONLY`. The championship gate therefore remains `HOLD` until those three matchups receive independent executable challengers and all five official blocks pass.

## Build one identity lock

```bash
python scripts/build_red_team_bundles.py \
  --cg-dir /ABSOLUTE/OFFICIAL/cg \
  --candidate-bundle /ABSOLUTE/EXTRACTED/CANDIDATE \
  --lock-out artifacts/red_team_manifest.lock.json
```

The lock binds one candidate tree SHA-256, one `libcg.so` SHA-256, and every opponent tree SHA-256. `promotion_sources.json` also freezes the exact historical commit, commit-owned package builder, policy identity and source PR for promotion-eligible challengers. Missing git history, a deck mismatch, a different engine, or any placeholder identity fails closed.

## Official evaluation

```bash
python scripts/run_official_red_team.py \
  --cg-dir /ABSOLUTE/OFFICIAL/cg \
  --candidate-bundle /ABSOLUTE/EXTRACTED/CANDIDATE \
  --manifest artifacts/red_team_manifest.lock.json
```

The runner verifies the actual imported `cg.game` directory, checks every bundled `libcg.so` against the locked engine, reloads both agents for every game, measures internal submission fallback, and uses a hard Python-decision watchdog. Runtime counters remain separate from wins.

The current production Bundle does not use Search API. `scripts/static_gate.py` enforces that absence; `search_resource_leak=0` is not accepted merely by leaving an uninstrumented counter at zero.

## Replay Mining training corpus

The 14 Replay Mining inputs are frozen by exact SHA-256 in `training_replay_corpus.json`. They cannot be reused as post-fix holdout evidence.

Corrected training baseline:

- 14 episodes: 11 losses / 3 wins;
- 54 cases: 1 causal / 17 direct / 36 candidate;
- `MEWTWO_SETUP_DELAY`: 43 — 7 direct and 36 candidate;
- `NO_BACKUP_AFTER_SPIDOPS`: 3 direct;
- `UNREADY_EX_EXPOSED`: 2 — one direct and one causal/FATAL;
- `NONPERSISTENT_DAMAGE_LOOP`: 3 direct;
- `DECK_OUT_CLOCK`: 3 direct.

Winning episodes and immediate Prize-taking KOs are excluded from loss-mode counts.

## Post-fix holdout Replay gate

```bash
python scripts/judge_replays.py NEW_1.json NEW_2.json NEW_3.json NEW_4.json NEW_5.json \
  --agent-name ジェニファー \
  --candidate-sha256 <LOCKED_CANDIDATE_TREE_SHA256> \
  --corpus-id postfix-holdout-001 \
  --corpus-kind POST_FIX_HOLDOUT
```

Promotion requires at least five unique post-fix Replay files and episode IDs, candidate SHA matching the official run, zero overlap with the frozen training corpus, zero fatal findings, and zero applicable canonical failure counts.

`BAD_SPREAD_TARGET` is explicitly not applicable to the current fixed Rocket Mewtwo deck because it has no spread-target action contract. It is not reported as supported merely because its count is zero.

## Promotion verdict

```bash
python scripts/promotion_gate.py \
  --manifest artifacts/red_team_manifest.lock.json \
  --results artifacts/official_red_team \
  --replay-summary artifacts/replay_judge/summary.json
```

The verdict stays `HOLD` unless all required opponent Bundles are promotion-grade, all exact identities match, all five blocks pass, at least 1,000 games complete, every runtime fault counter is zero, and the candidate-bound post-fix holdout gate passes.

No same-seed claim is made because the public CABT `battle_start` contract does not expose a controllable seed in this runner. Performance improvement still requires official execution and appropriately designed A/B evidence.
