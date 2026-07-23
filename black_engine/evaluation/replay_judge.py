from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from black_engine.championship_policy import ChampionshipRocketMewtwoPolicy, LONG_HORIZON_RESOURCE_CARDS
from black_engine.rocket_mewtwo_worldline import T_ATTACK, T_PLAY

from .models import DecisionFinding, EpisodeAudit

SEVERITY_PENALTY = {"FATAL": 25.0, "MAJOR": 8.0, "MINOR": 2.0}
DOMAIN_BY_CODE = {
    "ILLEGAL_RECORDED_ACTION": "runtime",
    "MANDATORY_EMPTY": "runtime",
    "TERMINAL_ACTION_MISS": "terminal",
    "PROMOTION_LETHAL_MISS": "promotion",
    "PRIZE_AWARE_ACTIVE_MISS": "promotion",
    "NONPERSISTENT_DAMAGE_REPEAT": "attack",
    "DECK_CLOCK_VIOLATION": "clock",
    "ATTACK_WITHOUT_BACKUP": "tempo",
}


def _agents(payload: dict) -> list[str]:
    info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
    agents = info.get("Agents") if isinstance(info.get("Agents"), list) else []
    return [str(value.get("Name", "")) if isinstance(value, dict) else "" for value in agents]


def _legal(obs: dict, action: Any) -> bool:
    select = obs.get("select") if isinstance(obs.get("select"), dict) else {}
    options = select.get("option") if isinstance(select.get("option"), list) else []
    minimum = max(0, int(select.get("minCount", 0) or 0))
    maximum_raw = select.get("maxCount", minimum)
    maximum = minimum if maximum_raw is None else max(0, int(maximum_raw))
    return (
        isinstance(action, list)
        and all(type(value) is int for value in action)
        and len(action) == len(set(action))
        and minimum <= len(action) <= maximum
        and all(0 <= value < len(options) for value in action)
    )


def _finding(
    *,
    step: int,
    turn: int,
    seat: int,
    code: str,
    severity: str,
    recorded: list[int],
    expected: list[int] | None,
    runner_id: str | None,
    evidence: dict[str, Any] | None = None,
) -> DecisionFinding:
    return DecisionFinding(
        step=step,
        turn=turn,
        seat=seat,
        code=code,
        severity=severity,
        recorded=list(recorded),
        expected=list(expected) if expected is not None else None,
        runner_id=runner_id,
        evidence=evidence or {},
    )


def audit_episode(path: str | Path, agent_name: str) -> EpisodeAudit:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    agents = _agents(payload)
    if agent_name not in agents:
        raise ValueError(f"agent {agent_name!r} not found; agents={agents}")
    seat = agents.index(agent_name)
    rewards = payload.get("rewards") if isinstance(payload.get("rewards"), list) else []
    reward = rewards[seat] if seat < len(rewards) else None
    audit = EpisodeAudit(
        episode_id=(payload.get("info") or {}).get("EpisodeId", payload.get("id", Path(path).stem)),
        agent_name=agent_name,
        seat=seat,
        reward=reward,
        result="WIN" if reward == 1 else "LOSS" if reward == -1 else "UNKNOWN",
    )
    policy = ChampionshipRocketMewtwoPolicy()
    counts: Counter[str] = Counter()

    steps = payload.get("steps") or []
    for step_index, pair in enumerate(steps[:-1]):
        if not isinstance(pair, list) or seat >= len(pair) or not isinstance(pair[seat], dict):
            continue
        row = pair[seat]
        if row.get("status") != "ACTIVE":
            continue
        obs = row.get("observation") if isinstance(row.get("observation"), dict) else None
        next_pair = steps[step_index + 1]
        next_row = next_pair[seat] if isinstance(next_pair, list) and seat < len(next_pair) and isinstance(next_pair[seat], dict) else {}
        action = next_row.get("action")
        if not isinstance(obs, dict) or not isinstance(obs.get("select"), dict):
            continue
        options = obs["select"].get("option") if isinstance(obs["select"].get("option"), list) else []
        minimum = max(0, int(obs["select"].get("minCount", 0) or 0))
        if minimum > 0 and not options:
            current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
            turn = int(current.get("turn", 0) or 0)
            audit.findings.append(
                _finding(
                    step=step_index,
                    turn=turn,
                    seat=seat,
                    code="MANDATORY_EMPTY",
                    severity="FATAL",
                    recorded=action if isinstance(action, list) else [],
                    expected=None,
                    runner_id=None,
                    evidence={"context": obs["select"].get("context")},
                )
            )
            counts["MANDATORY_EMPTY"] += 1
            continue
        if not options:
            continue

        audit.decisions += 1
        current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
        turn = int(current.get("turn", 0) or 0)
        recorded = action if isinstance(action, list) else []
        if not _legal(obs, recorded):
            audit.findings.append(
                _finding(
                    step=step_index,
                    turn=turn,
                    seat=seat,
                    code="ILLEGAL_RECORDED_ACTION",
                    severity="FATAL",
                    recorded=recorded,
                    expected=None,
                    runner_id=None,
                    evidence={
                        "min": obs["select"].get("minCount"),
                        "max": obs["select"].get("maxCount"),
                        "options": len(options),
                    },
                )
            )
            counts["ILLEGAL_RECORDED_ACTION"] += 1
            continue
        audit.legal_decisions += 1

        context = policy.build_context(obs)
        truth = context["truth"]
        terminal = policy._terminal_attack(context)
        promotion = policy._promotion_choice(context)
        actual = recorded[0] if len(recorded) == 1 else None

        if terminal is not None and actual != terminal:
            audit.findings.append(
                _finding(
                    step=step_index,
                    turn=turn,
                    seat=seat,
                    code="TERMINAL_ACTION_MISS",
                    severity="FATAL",
                    recorded=recorded,
                    expected=[terminal],
                    runner_id="TERMINAL_ACTION_FREEZE",
                    evidence={"opponent_hp": context["opponent_hp"], "our_prizes": truth.our_prizes},
                )
            )
            counts["TERMINAL_ACTION_MISS"] += 1
        elif promotion is not None and actual != promotion:
            code = "PROMOTION_LETHAL_MISS" if policy.last_runner_id == "PROMOTION_LETHAL_OVERRIDE" else "PRIZE_AWARE_ACTIVE_MISS"
            severity = "FATAL" if code == "PROMOTION_LETHAL_MISS" else "MAJOR"
            audit.findings.append(
                _finding(
                    step=step_index,
                    turn=turn,
                    seat=seat,
                    code=code,
                    severity=severity,
                    recorded=recorded,
                    expected=[promotion],
                    runner_id=policy.last_runner_id,
                    evidence={"observed_opponent_damage": context["observed_opponent_damage"]},
                )
            )
            counts[code] += 1

        if actual is not None and 0 <= actual < len(truth.options):
            chosen = truth.options[actual]
            plan = policy._plan_for_option(actual, context)
            if plan.plan.plan_id == "REJECT_NONPERSISTENT_DAMAGE":
                audit.findings.append(
                    _finding(step=step_index, turn=turn, seat=seat, code="NONPERSISTENT_DAMAGE_REPEAT", severity="MAJOR", recorded=recorded, expected=None, runner_id=plan.plan.plan_id)
                )
                counts["NONPERSISTENT_DAMAGE_REPEAT"] += 1
            if plan.plan.plan_id == "ATTACK_WITHOUT_BACKUP":
                audit.findings.append(
                    _finding(step=step_index, turn=turn, seat=seat, code="ATTACK_WITHOUT_BACKUP", severity="MAJOR", recorded=recorded, expected=None, runner_id=plan.plan.plan_id)
                )
                counts["ATTACK_WITHOUT_BACKUP"] += 1
            if context["deck_clock_critical"] and chosen.action_type == T_PLAY and chosen.card_id in LONG_HORIZON_RESOURCE_CARDS:
                audit.findings.append(
                    _finding(
                        step=step_index,
                        turn=turn,
                        seat=seat,
                        code="DECK_CLOCK_VIOLATION",
                        severity="MAJOR",
                        recorded=recorded,
                        expected=None,
                        runner_id="DECK_CLOCK_SUPPRESS_RESOURCE",
                        evidence={"deck_count": context["deck_count"], "safe_draw_budget": context["safe_draw_budget"]},
                    )
                )
                counts["DECK_CLOCK_VIOLATION"] += 1
            if chosen.action_type == T_ATTACK:
                active = truth.active
                target = truth.opponent_active
                if active is not None and target is not None:
                    policy._pending_attack = (
                        active.card_id,
                        chosen.attack_id,
                        target.serial,
                        target.card_id,
                        target.current_hp,
                        truth.turn,
                    )

    domains = {"runtime": 100.0, "terminal": 100.0, "promotion": 100.0, "attack": 100.0, "clock": 100.0, "tempo": 100.0}
    total_penalty = 0.0
    for finding in audit.findings:
        penalty = SEVERITY_PENALTY.get(finding.severity, 0.0)
        total_penalty += penalty
        domain = DOMAIN_BY_CODE.get(finding.code)
        if domain:
            domains[domain] = max(0.0, domains[domain] - penalty)
    audit.domain_scores = domains
    audit.overall_score = max(0.0, 100.0 - total_penalty)
    audit.metadata = {"finding_counts": dict(counts), "source": str(Path(path))}
    return audit
