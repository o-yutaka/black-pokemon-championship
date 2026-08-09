from __future__ import annotations

"""Post-match analytics for official-CABT Agent-vs-Agent runs.

This module deliberately does not implement a second card-game engine. It only
consumes observations/results produced by the official engine and turns them
into evidence for BLACK's research loop.
"""

from dataclasses import dataclass, asdict
from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Iterable


@dataclass
class Rating:
    mu: float = 25.0
    sigma: float = 8.333


class SkillRating:
    """Small dependency-free μ/σ rating tracker for local official matches.

    It is a research rating, not a claim that it reproduces Kaggle's private
    matchmaking implementation byte-for-byte. Official competition results
    remain the promotion truth.
    """

    def __init__(self, ratings: dict[str, Rating] | None = None) -> None:
        self.ratings = ratings or {}

    def get(self, agent: str) -> Rating:
        return self.ratings.setdefault(agent, Rating())

    def expected(self, a: str, b: str) -> float:
        ra, rb = self.get(a), self.get(b)
        scale = math.sqrt(1.0 + ra.sigma * ra.sigma + rb.sigma * rb.sigma)
        return 1.0 / (1.0 + math.exp(-(ra.mu - rb.mu) / max(1.0, scale)))

    def update(self, winner: str, loser: str, draw: bool = False) -> None:
        rw, rl = self.get(winner), self.get(loser)
        p = self.expected(winner, loser)
        score = 0.5 if draw else 1.0
        k = max(0.5, min(4.0, (rw.sigma + rl.sigma) / 8.0))
        delta = k * (score - p)
        rw.mu += delta
        rl.mu -= delta
        rw.sigma = max(1.0, rw.sigma * 0.999)
        rl.sigma = max(1.0, rl.sigma * 0.999)

    def nearest_opponent(self, agent: str) -> str | None:
        if agent not in self.ratings:
            return None
        return min(
            (name for name in self.ratings if name != agent),
            key=lambda name: abs(self.get(name).mu - self.get(agent).mu),
            default=None,
        )

    def snapshot(self) -> dict[str, dict[str, float]]:
        return {k: asdict(v) for k, v in sorted(self.ratings.items())}


class MatchupMatrix:
    def __init__(self) -> None:
        self.games: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])

    def record(self, winner: str, loser: str, draw: bool = False) -> None:
        if draw:
            self.games[(winner, loser)][0] += 1
            self.games[(loser, winner)][0] += 1
            return
        self.games[(winner, loser)][0] += 1
        self.games[(loser, winner)][1] += 1

    def win_rate(self, a: str, b: str) -> float | None:
        wins, losses = self.games.get((a, b), [0, 0])
        total = wins + losses
        return wins / total if total else None

    def snapshot(self) -> list[dict[str, Any]]:
        rows = []
        for (a, b), (wins, losses) in sorted(self.games.items()):
            rows.append({"agent_a": a, "agent_b": b, "wins": wins, "losses": losses,
                         "games": wins + losses,
                         "win_rate": wins / (wins + losses) if wins + losses else None})
        return rows


@dataclass
class DecisionTrace:
    game_id: str
    agent: str
    opponent: str
    turn: int
    state_hash: str
    context: str | None
    legal_actions: list[Any]
    selected_action: Any
    alternative_actions: list[Any]
    result: int | None = None
    prize_delta: int | None = None
    score: float | None = None


class DecisionTraceStore:
    def __init__(self) -> None:
        self.rows: list[DecisionTrace] = []

    @staticmethod
    def state_hash(observation: Any) -> str:
        payload = json.dumps(observation, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(payload.encode()).hexdigest()[:20]

    def record(self, game_id: str, agent: str, opponent: str, turn: int,
               observation: dict[str, Any], selected_action: Any,
               result: int | None = None) -> DecisionTrace:
        current = observation.get("current") if isinstance(observation, dict) else {}
        options = current.get("select", {}).get("option", []) if isinstance(current, dict) else []
        context = current.get("select", {}).get("type") if isinstance(current, dict) else None
        row = DecisionTrace(
            game_id=game_id, agent=agent, opponent=opponent, turn=turn,
            state_hash=self.state_hash(observation), context=context,
            legal_actions=list(options) if isinstance(options, list) else [],
            selected_action=selected_action,
            alternative_actions=[x for x in (options if isinstance(options, list) else []) if x != selected_action][:8],
            result=result,
        )
        self.rows.append(row)
        return row

    def save_jsonl(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            for row in self.rows:
                f.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")


class WeakPositionMiner:
    """Find repeated decision states correlated with losses.

    A state is only promoted to a weak-position candidate after it appears
    repeatedly; a single loss is never treated as proof of a bad policy.
    """

    def __init__(self, min_occurrences: int = 3) -> None:
        self.min_occurrences = min_occurrences

    def mine(self, traces: Iterable[DecisionTrace]) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for t in traces:
            b = buckets.setdefault(t.state_hash, {"state_hash": t.state_hash,
                "agent": t.agent, "opponent": t.opponent, "turn": t.turn,
                "visits": 0, "losses": 0, "actions": defaultdict(int)})
            b["visits"] += 1
            b["losses"] += int(t.result == 1)
            b["actions"][str(t.selected_action)] += 1
        out = []
        for b in buckets.values():
            if b["visits"] < self.min_occurrences or not b["losses"]:
                continue
            out.append({"state_hash": b["state_hash"], "agent": b["agent"],
                        "opponent": b["opponent"], "turn": b["turn"],
                        "visits": b["visits"], "losses": b["losses"],
                        "loss_rate": b["losses"] / b["visits"],
                        "actions": dict(b["actions"])})
        return sorted(out, key=lambda x: (-x["loss_rate"], -x["visits"]))


@dataclass
class CounterfactualCandidate:
    game_id: str
    state_hash: str
    selected_action: Any
    alternative_action: Any
    status: str = "RECORDED_ONLY"
    observed_result: int | None = None
    counterfactual_result: int | None = None
    evidence: str = ""


class CounterfactualLedger:
    """Stores alternatives without pretending they were executed.

    Execution of an alternative is only marked COMPLETE when a caller has
    replayed that exact state through the official engine. This prevents an
    internal approximation from being confused with official-engine truth.
    """

    def __init__(self) -> None:
        self.rows: list[CounterfactualCandidate] = []

    def add(self, trace: DecisionTrace, alternative_action: Any) -> CounterfactualCandidate:
        row = CounterfactualCandidate(trace.game_id, trace.state_hash,
                                      trace.selected_action, alternative_action)
        self.rows.append(row)
        return row

    def complete(self, index: int, result: int, evidence: str) -> None:
        row = self.rows[index]
        row.status = "OFFICIAL_REPLAY_COMPLETE"
        row.counterfactual_result = result
        row.evidence = evidence


class ChampionshipAnalysis:
    """Single aggregate object for the official-match research layer."""

    def __init__(self) -> None:
        self.matchups = MatchupMatrix()
        self.ratings = SkillRating()
        self.traces = DecisionTraceStore()
        self.counterfactuals = CounterfactualLedger()
        self.weak = WeakPositionMiner()

    def record_match(self, agent_a: str, agent_b: str, result: int) -> None:
        if result not in (0, 1):
            raise ValueError("result must be 0 (A wins) or 1 (B wins)")
        winner, loser = (agent_a, agent_b) if result == 0 else (agent_b, agent_a)
        self.matchups.record(winner, loser)
        self.ratings.update(winner, loser)

    def report(self) -> dict[str, Any]:
        return {
            "matchup_matrix": self.matchups.snapshot(),
            "skill_rating": self.ratings.snapshot(),
            "weak_positions": self.weak.mine(self.traces.rows),
            "counterfactuals": [asdict(x) for x in self.counterfactuals.rows],
            "decision_trace_count": len(self.traces.rows),
        }

    def save_report(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.report(), ensure_ascii=False, indent=2), encoding="utf-8")
