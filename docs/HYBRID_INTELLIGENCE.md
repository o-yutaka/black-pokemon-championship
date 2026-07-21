# BLACK Hybrid Intelligence v1

## Pipeline

```text
CABT Observation + select.option
  -> Canonical TruthState (public/self information only)
  -> Bayesian archetype posterior
  -> hidden-zone determinization
  -> SO-ISMCTS through documented cg.api Search API
  -> evidence-trained tabular RL prior
  -> deck-specific Planner Arena
  -> hard/soft composite guards
  -> Hybrid Judge
  -> legal option index list
```

## Truth rules

- Opponent hand contents are never copied into TruthState; only `handCount` is retained.
- Attached Energy, tools, and visible evolution-stack cards are counted outside hidden decks.
- Bayesian hidden states require evidence-backed 60-card templates. No template means Search disabled.
- RL files ship neutral with `trained=false`; they cannot influence ranking before training.
- ISMCTS uses only `search_begin`, `search_step`, `search_release`, and `search_end`.
- Multi-select remains with the validated card-specific base policy until exact effect contexts are captured.
- Every enhancement fails closed to the deterministic deck policy.

## Composite score

```text
base deck heuristic
+ evidence-trained RL Q prior
+ visit-weighted ISMCTS value
+ Planner Arena votes
+ Guard bonuses/penalties
- hard-vetoed actions
```

Search influence is discounted when Bayesian confidence or visit count is low.

## Candidate guards

### Mewtwo / Spidops

- Reject Mewtwo attacks before four Team Rocket bodies.
- Penalize nonterminal Spidops reservoir exhaustion.
- Preserve the minimum 160/220/280 discard route.
- Prefer Wobbuffet conversion when it avoids unnecessary ex exposure.

### Garchomp / Spiritomb

- Penalize nonlethal heavy attacks that destroy follow-up Energy.
- Prefer the sustainable 100 + draw-to-six route when 260 is not decisive.
- Boost exact Spiritomb lethal handoff.
- Reject END when the Spiritomb terminal route is available.

## Build evidence-backed belief bank

```bash
python scripts/build_belief_bank.py \
  --template GARCH=/path/to/garchomp/deck.csv \
  --template MEWTWO=/path/to/mewtwo/deck.csv \
  --output models/opponent_belief_bank.json
```

## Train RL prior

Input JSONL fields:

```json
{"episode_id":"e1","state_key":"...","action_signature":"...","reward":0.0}
```

Train:

```bash
python scripts/train_rl_prior.py \
  --input artifacts/rl_transitions.jsonl \
  --output models/rl_prior_mewtwo_spidops.json
```

Terminal result should supply the final reward. Training completion is not promotion evidence; held-out paired evaluation remains mandatory.

## Runtime controls

```text
BLACK_ISMCTS=0|1
BLACK_ISMCTS_SIMS=48
BLACK_ISMCTS_MS=35
BLACK_ISMCTS_DEPTH=8
BLACK_BELIEF_BANK=/path/to/bank.json
BLACK_DECISION_TRACE=/path/to/decisions.jsonl
CABT_CG_DIR=/home/user/HROS/submission/cg
```
