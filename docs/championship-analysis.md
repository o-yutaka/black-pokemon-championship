# BLACK Championship Analysis Layer

This layer sits **above the official CABT engine**. It does not implement a second Pokémon TCG simulator.

## Canonical flow

```text
Official CABT
    |
    +--> Agent A vs Agent B
    |
    +--> official observation / legal options
    |
    +--> result
          |
          v
  ChampionshipAnalysis
    |
    +--> Matchup Matrix
    +--> Skill Rating (local μ/σ research state)
    +--> Decision Trace
    +--> Counterfactual Ledger
    +--> Weak Position Mining
          |
          v
     BLACK Evolution
```

## 1. Matchup Matrix

Records actual Agent-vs-Agent results from official-engine matches.

It is not a synthetic deck-vs-deck table and must not create matches outside the official engine contract.

## 2. Skill Rating

Maintains a lightweight local μ/σ research rating so the PC lab can choose opponents near an Agent's current strength and prioritize informative matches.

This is explicitly a **local research rating**, not a claim that the exact Kaggle matchmaking implementation is reproduced.

Official Kaggle results remain authoritative.

## 3. Decision Trace

For every BLACK-controlled decision, preserve:

- game id
- agent / opponent
- turn
- state hash
- selection context
- legal options exposed by CABT
- selected option
- alternative legal options
- final result when available

The trace is observation evidence, not a second rules engine.

## 4. Counterfactual

Every decision can register alternative legal actions as candidates.

A candidate starts as:

```text
RECORDED_ONLY
```

It becomes:

```text
OFFICIAL_REPLAY_COMPLETE
```

only after that exact state/action is replayed through the official engine and the evidence is attached.

Therefore BLACK never reports a hypothetical simulator result as an official result.

## 5. Weak Position Mining

Repeated state hashes are grouped and correlated with losses.

A state is only promoted when it reaches the configured minimum occurrence count. This prevents one unlucky game from becoming a false policy rule.

Output includes:

- state hash
- agent / opponent
- turn
- visits
- losses
- loss rate
- actions selected

## 6. PC research loop

```text
Official CABT Agent-vs-Agent
        |
        v
Decision Trace
        |
        +--> Matchup Matrix
        +--> Skill Rating
        +--> Weak Position Mining
        +--> Counterfactual candidates
        |
        v
BLACK hypothesis
        |
        v
policy mutation
        |
        v
Official CABT A/B
        |
        v
accept / reject
```

The PC layer can run many official-engine matches in parallel for speed, but it must not substitute a custom game engine, custom legality model, or synthetic outcome generator.

## Evidence hierarchy

1. Official Kaggle result
2. Official CABT replay/result
3. Controlled local official-engine A/B
4. Trace-derived hypothesis
5. Unexecuted counterfactual candidate

Lower levels must never be presented as higher-level evidence.
