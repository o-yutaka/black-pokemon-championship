from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RuntimeCounters:
    completed: int = 0
    crash: int = 0
    runtime_error: int = 0
    illegal_action: int = 0
    mandatory_empty: int = 0
    timeout: int = 0
    fallback: int = 0
    search_resource_leak: int = 0

    @property
    def clean(self) -> bool:
        return all(value == 0 for key, value in asdict(self).items() if key != "completed")

    def merge(self, other: "RuntimeCounters") -> None:
        for key in asdict(self):
            setattr(self, key, getattr(self, key) + getattr(other, key))


@dataclass(frozen=True)
class DecisionFinding:
    step: int
    turn: int
    seat: int
    code: str
    severity: str
    recorded: list[int]
    expected: list[int] | None
    runner_id: str | None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class EpisodeAudit:
    episode_id: int | str
    agent_name: str
    seat: int
    reward: float | int | None
    result: str
    decisions: int = 0
    legal_decisions: int = 0
    findings: list[DecisionFinding] = field(default_factory=list)
    domain_scores: dict[str, float] = field(default_factory=dict)
    overall_score: float = 100.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["findings"] = [asdict(value) for value in self.findings]
        return payload


@dataclass
class GameRecord:
    matchup: str
    candidate_bundle_sha256: str
    opponent_bundle_sha256: str
    candidate_seat: int
    winner_seat: int | None
    result: str
    steps: int
    decision_ms: list[float]
    runtime: RuntimeCounters
    error: str | None = None

    @property
    def candidate_win(self) -> bool:
        return self.winner_seat == self.candidate_seat

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidate_win"] = self.candidate_win
        return payload


@dataclass
class MatchupSummary:
    matchup: str
    games: int
    wins: int
    losses: int
    draws_or_errors: int
    seat0_games: int
    seat1_games: int
    seat0_wins: int
    seat1_wins: int
    win_rate: float
    wilson_low: float
    wilson_high: float
    runtime: RuntimeCounters
    mean_decision_ms: float
    p95_decision_ms: float
    evidence_mode: str = "PROMOTION"
    candidate_bundle_sha256: str = ""
    opponent_bundle_sha256: str = ""
    engine_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["runtime"] = asdict(self.runtime)
        return payload
