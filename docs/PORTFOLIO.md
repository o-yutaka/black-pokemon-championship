# Portfolio Contract — BLACK Pokémon Championship

## Positioning

This repository is the planning, simulation, evaluation, and strict external-engine proof in the portfolio. The domain is a trading-card-game competition; the transferable engineering is stateful decision-making under a hostile or constrained execution contract.

## Hiring evidence

- External engine action contract validation
- Stateful deterministic policy
- Legal-action selection boundary
- Timeout and exception containment
- Deterministic fallback
- Decision overlay and warnings
- Reproducible submission packaging
- Static deployment gate
- Isolated raw-exec verification
- Fast regression/crash/speed screening
- Honest separation between local screening and official evaluation

## Transfer map

```text
Engine options        → allowed business tools
State + resources     → workflow state
Policy scoring        → agent planning
Legal validator       → contract/permission gate
Fallback              → failure recovery
Replay/evaluation     → agent evaluation harness
Submission artifact   → reproducible deployment
```

## Recruiter path

1. Read `README.md`.
2. Inspect `black_engine/runtime.py`.
3. Inspect `scripts/static_gate.py`.
4. Inspect `black_engine/policy.py`.
5. Run the verification commands.

## Claim boundary

Fast evaluation is a regression/crash/speed screen, not leaderboard evidence. The project does not claim that the domain heuristic is a universal planner.
