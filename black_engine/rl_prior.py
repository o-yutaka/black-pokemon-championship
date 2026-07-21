from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .truth import LegalOption, TruthState


@dataclass(frozen=True)
class RLPriorScore:
    value: float
    trained: bool
    samples: int
    source: str


@dataclass
class TabularQPrior:
    q_values: dict[str, float] = field(default_factory=dict)
    visits: dict[str, int] = field(default_factory=dict)
    trained: bool = False
    source: str = "untrained-neutral"

    @staticmethod
    def state_key(truth: TruthState) -> str:
        my_active = truth.me.active[0].card_id if truth.me.active else -1
        opp_active = truth.opponent.active[0].card_id if truth.opponent.active else -1
        prize_visible = sum(value is not None for value in truth.me.prize_ids)
        return ":".join(map(str, (
            truth.actor,
            min(truth.turn, 12),
            my_active,
            opp_active,
            len(truth.me.bench),
            len(truth.opponent.bench),
            truth.me.hand_count,
            truth.opponent.hand_count,
            truth.me.deck_count // 5,
            truth.opponent.deck_count // 5,
            prize_visible,
        )))

    @classmethod
    def action_key(cls, truth: TruthState, option: LegalOption) -> str:
        return f"{cls.state_key(truth)}|{option.signature}"

    def score(self, truth: TruthState, option: LegalOption) -> RLPriorScore:
        key = self.action_key(truth, option)
        return RLPriorScore(
            value=float(self.q_values.get(key, 0.0)),
            trained=self.trained,
            samples=int(self.visits.get(key, 0)),
            source=self.source,
        )

    def update_episode(self, transitions: Iterable[tuple[str, str, float]], *, gamma: float = 0.99, alpha: float = 0.15) -> None:
        if not (0 < alpha <= 1):
            raise ValueError("alpha must be in (0, 1]")
        if not (0 <= gamma <= 1):
            raise ValueError("gamma must be in [0, 1]")
        items = list(transitions)
        return_value = 0.0
        for state_key, action_signature, reward in reversed(items):
            return_value = float(reward) + gamma * return_value
            key = f"{state_key}|{action_signature}"
            old = self.q_values.get(key, 0.0)
            self.q_values[key] = old + alpha * (return_value - old)
            self.visits[key] = self.visits.get(key, 0) + 1
        if items:
            self.trained = True
            self.source = "offline-monte-carlo-return"

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({
            "version": 1,
            "trained": self.trained,
            "source": self.source,
            "q_values": self.q_values,
            "visits": self.visits,
        }, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path | None) -> "TabularQPrior":
        if path is None or not Path(path).is_file():
            return cls()
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            q_values={str(k): float(v) for k, v in dict(payload.get("q_values") or {}).items()},
            visits={str(k): int(v) for k, v in dict(payload.get("visits") or {}).items()},
            trained=bool(payload.get("trained", False)),
            source=str(payload.get("source") or "loaded"),
        )
