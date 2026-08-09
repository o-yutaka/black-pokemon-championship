# BLACK × ptcg-abc Integration Directive

## Purpose

Integrate the reusable engineering patterns from `wmh/ptcg-abc` into BLACK without replacing or weakening the canonical championship runtime.

`ptcg-abc` is treated as an external policy/research source, not as a replacement for BLACK Core, Runtime, Submission Contract, or the official CABT engine.

## Canonical principle

```text
Architecture serves decisions.
Decisions serve truth.
Truth serves reality.
Nothing serves architecture.
```

The current official engine-provided selection contract remains the only legal execution authority.

## Target architecture

```text
                         BLACK CORE
                             |
                             v
                    STRATEGY / META
                             |
                             v
                  COUNTERFACTUAL SEARCH
                             |
                             v
                PTCG POLICY / HEURISTICS
                    |                    |
                    |                    +--> ptcg-abc-derived research
                    |                         - SelectContext scoring
                    |                         - normalization
                    |                         - tactical heuristics
                    |                         - legal fallback patterns
                    |
                    v
                LEGAL ACTION GATE
                    |
                    v
             OFFICIAL CABT ENGINE
                    |
                    v
              RESULT / OBSERVATION
                    |
              +-----+------+
              |            |
              v            v
           SCORER        MEMORY
              |            |
              +-----+------+
                    v
              EVOLUTION / A-B
                    |
                    +------> candidate policy
```

## Non-negotiable boundaries

Do not:

- copy the entire `ptcg-abc` repository into the canonical submission
- replace BLACK Core, Runtime, Scorer, Memory, or Evolution
- replace `submission_contract.py`
- modify the official CABT legality boundary
- introduce an alternate runtime router into the canonical bundle
- introduce runtime deck switching into the current fixed-deck submission
- treat local simulation as official leaderboard evidence
- remove existing tests or verification gates to accommodate the integration

The current repository remains a single reviewed Dragapult-family submission with one canonical deck policy.

## What to absorb from ptcg-abc

### 1. Policy layer patterns

Use `ptcg-abc` as a baseline for context-specific decision scoring. The conceptual flow is:

```text
current observation
    -> SelectContext
    -> candidate option scoring
    -> normalized selection
    -> legal action gate
```

Any imported scoring logic must be adapted to the current BLACK policy interface rather than bypassing the runtime boundary.

### 2. Legal fallback

Preserve the repository's existing deterministic fallback as the final authority. `ptcg-abc`-derived logic may propose actions, but failure must degrade safely:

```text
policy exception
policy timeout
invalid policy output
unknown state
        |
        v
current engine selection contract
        |
        v
legal deterministic fallback
```

The fallback must derive only from currently exposed legal options. It must never invent an action.

### 3. Selection normalization

Introduce normalization only inside the policy/research boundary:

```text
raw candidate
    -> normalize
    -> candidate option indexes
    -> runtime legality validation
```

Runtime legality remains unchanged.

### 4. A/B evaluation

`ptcg-abc`'s A/B evaluation pattern should inform BLACK's experiment loop:

```text
baseline
  -> one hypothesis
  -> one policy mutation
  -> controlled evaluation
  -> result comparison
  -> accept / reject
```

Do not promote a policy because it looks more sophisticated. Promote only when the evidence shows improvement under the appropriate evaluation gate.

## Counterfactual extension

The existing deterministic policy can later be extended without changing the execution boundary:

```text
legal candidate A -> opponent responses -> outcome distribution
legal candidate B -> opponent responses -> outcome distribution
                                      |
                                      v
                               BLACK Scorer
```

Candidate score may combine:

```text
baseline heuristic
+ win-condition value
+ board / resource value
+ future-option value
+ counterfactual expected value
- risk penalty
```

The exact scoring model must remain an experiment until supported by evidence.

## Meta analysis boundary

`ptcg-abc` strategy and meta material belongs in research/knowledge, not as uncontrolled hard-coded runtime branching.

Preferred flow:

```text
external meta evidence
      -> structured MetaSnapshot
      -> hypothesis
      -> policy candidate
      -> controlled evaluation
      -> promotion decision
```

A deck-policy change is not part of the canonical runtime unless it is explicitly reviewed and proven compatible with the fixed submission contract.

## Research adapters

MCTS, RL, imitation learning, or other experimental material from `ptcg-abc` must remain isolated from production until independently validated.

Recommended boundary:

```text
research/
  ptcg_abc/
    mcts_adapter/
    rl_adapter/
    imitation_adapter/
```

These adapters produce candidate policies or scores. They do not directly execute CABT actions.

## Evidence hierarchy

Use the following evidence order:

1. Official Kaggle leaderboard / ladder evidence
2. Official CABT evaluation
3. Controlled local A/B evaluation
4. Regression / replay evaluation
5. Internal simulator results
6. Heuristic or model judgement

A lower-level result must never be presented as stronger evidence than a higher-level result.

## Memory / learning record

For high-value decisions, preserve structured evidence such as:

```json
{
  "state_hash": "...",
  "turn": 0,
  "candidate_actions": [],
  "selected_action": 0,
  "alternative_action": 0,
  "score_delta": 0.0,
  "result": "win",
  "policy_source": "black|ptcg_abc|hybrid",
  "confidence": 0.0,
  "lesson": "..."
}
```

Persist novel, high-impact, repeated-error, meta-shift, and policy-contradiction cases preferentially.

## Self-negation requirement

For material policy decisions, evaluate:

```text
selected action
why it is correct
why it could be wrong
best alternative
opponent counter
whether the decision changes under that counter
```

This is an internal decision-quality check; it does not weaken the external legality contract.

## Implementation sequence

### Phase 1 — Read-only analysis

Review `ptcg-abc` components relevant to:

- agent contract
- selection normalization
- context-specific scoring
- legal fallback
- CABT evaluation
- A/B evaluation
- strategy/meta analysis
- research experiments

No canonical BLACK runtime changes in this phase.

### Phase 2 — Adapter

Create a BLACK-side adapter only where an actual reusable interface is identified.

```text
ptcg-abc-derived logic
        -> BLACK Policy Interface
        -> existing Runtime
```

### Phase 3 — Baseline comparison

Compare the current BLACK policy against the adapted baseline under controlled evaluation.

Required measurements include:

- illegal action rate
- fallback rate
- exception rate
- timeout rate
- win/loss result
- decision score where available
- regression cases

### Phase 4 — Counterfactual research

Add simulation/search only behind the Policy boundary and compare against the baseline.

### Phase 5 — Promotion

Only evidence-backed improvements may cross into the canonical submission path.

## Verification requirements

Every integration change must preserve:

```text
python scripts/static_gate.py
python -m pytest -q
python scripts/build_submission.py ...
```

The exact current repository gates remain authoritative.

## Final rule

`ptcg-abc` contributes **proven policy patterns and research material**.

BLACK contributes **decision arbitration, evidence discipline, counterfactual analysis, memory, evolution, and promotion control**.

The official CABT engine remains the **execution truth boundary**.

The canonical championship artifact remains **single, reproducible, fixed-contract, and safe under policy failure**.
