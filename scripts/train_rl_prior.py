from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.rl_prior import TabularQPrior


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the offline BLACK tabular RL prior from evidence traces.")
    parser.add_argument("--input", required=True, help="JSONL with episode_id, state_key, action_signature, reward")
    parser.add_argument("--output", required=True)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--alpha", type=float, default=0.15)
    args = parser.parse_args()

    episodes: dict[str, list[tuple[str, str, float]]] = {}
    with Path(args.input).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            try:
                episode_id = str(row["episode_id"])
                transition = (
                    str(row["state_key"]),
                    str(row["action_signature"]),
                    float(row.get("reward", 0.0)),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise SystemExit(f"line {line_number}: invalid transition: {exc}") from exc
            episodes.setdefault(episode_id, []).append(transition)

    prior = TabularQPrior()
    for transitions in episodes.values():
        prior.update_episode(transitions, gamma=args.gamma, alpha=args.alpha)
    prior.save(args.output)
    print(json.dumps({
        "verdict": "RL_PRIOR_TRAINED" if prior.trained else "RL_PRIOR_EMPTY",
        "episodes": len(episodes),
        "state_actions": len(prior.q_values),
        "output": str(Path(args.output).resolve()),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
