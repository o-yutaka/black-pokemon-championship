from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from black_engine.championship_policy import ChampionshipRocketMewtwoPolicy, LONG_HORIZON_RESOURCE_CARDS
from black_engine.rocket_mewtwo_worldline import T_ATTACK, T_ENERGY, T_PLAY

from .models import DecisionFinding, EpisodeAudit
from .taxonomy import canonical_failure_counts

SEVERITY_PENALTY = {"FATAL": 25.0, "MAJOR": 8.0, "MINOR": 2.0}
DOMAIN_BY_CODE = {
    "ILLEGAL_RECORDED_ACTION": "runtime",
    "MANDATORY_EMPTY": "runtime",
    "TERMINAL_ACTION_MISS": "terminal",
    "LETHAL_ACTION_MISS": "terminal",
    "PROMOTION_LETHAL_MISS": "promotion",
    "PRIZE_AWARE_ACTIVE_MISS": "promotion",
    "ENERGY_ATTACH_SUBOPTIMAL": "energy",
    "SPREAD_TARGET_REGRET": "spread",
    "NONPERSISTENT_DAMAGE_REPEAT": "attack",
    "DECK_CLOCK_VIOLATION": "clock",
    "ATTACK_WITHOUT_BACKUP": "tempo",
}

BAD_ENERGY_PLAN_IDS = frozenset(
    {
        "UNRESOLVED_ENERGY_TARGET",
        "ILLEGAL_ROCKET_ENERGY_TARGET",
        "READY_MEWTWO_OVERATTACH",
        "BATTERY_BEFORE_ATTACKER",
        "PROTECT_TEAM_ROCKET_ENERGY",
        "LOW_VALUE_ATTACHMENT",
    }
)


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


def _trace_failure_codes(*values: Any) -> set[str]:
    """Read optional local decision traces without inventing replay evidence.

    Official Kaggle replays do not expose deck-specific counterfactual scores. A
    local Bundle may persist a trace alongside an observation; this hook lets a
    Dragapult adapter report SPREAD_TARGET_REGRET while raw official replays stay
    honestly unclassified for that deck-specific failure.
    """

    result: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            continue
        candidates = [value]
        for key in ("black_trace", "decision_trace", "evaluation"):
            nested = value.get(key)
            if isinstance(nested, dict):
                candidates.append(nested)
        for candidate in candidates:
            one = candidate.get("failure_code")
            many = candidate.get("failure_codes")
            if isinstance(one, str):
                result.add(one)
            if isinstance(many, list):
                result.update(item for item in many if isinstance(item, str))
    return result


def _best_lethal_attack(policy: ChampionshipRocketMewtwoPolicy, context: dict) -> int | None:
    truth = context["truth"]
    target = truth.opponent_active
    if target is None:
        return None
    lethal: list[tuple[int, int]] = []
    for option in truth.options:
        if option.action_type != T_ATTACK:
            continue
        damage = policy._attack_option_damage(option, context)
        if damage >= target.current_hp > 0:
            lethal.append((damage, option.action_index))
    return max(lethal, default=(0, -1))[1] if lethal else None


def _best_energy_action(policy: ChampionshipRocketMewtwoPolicy, context: dict) -> tuple[int | None, Any | None]:
    truth = context["truth"]
    candidates = [
        policy._plan_for_option(option.action_index, context)
        for option in truth.options
        if option.action_type == T_ENERGY
    ]
    if not candidates:
        return None, None
    best = policy.judge.choose(candidates)
    return best.plan.root_action_index, best


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
        lethal = None if terminal is not None else _best_lethal_attack(policy, context)
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
        elif lethal is not None and actual != lethal:
            audit.findings.append(
                _finding(
                    step=step_index,
                    turn=turn,
                    seat=seat,
                    code="LETHAL_ACTION_MISS",
                    severity="MAJOR",
                    recorded=recorded,
                    expected=[lethal],
                    runner_id="IMMEDIATE_KO_CHECK",
                    evidence={"opponent_hp": context["opponent_hp"], "our_prizes": truth.our_prizes},
                )
            )
            counts["LETHAL_ACTION_MISS"] += 1
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
            if chosen.action_type == T_ENERGY and plan.plan.plan_id in BAD_ENERGY_PLAN_IDS:
                best_index, best_plan = _best_energy_action(policy, context)
                if best_index is not None and best_index != actual and best_plan is not None:
                    audit.findings.append(
                        _finding(
                            step=step_index,
                            turn=turn,
                            seat=seat,
                            code="ENERGY_ATTACH_SUBOPTIMAL",
                            severity="MAJOR",
                            recorded=recorded,
                            expected=[best_index],
                            runner_id=best_plan.plan.plan_id,
                            evidence={
                                "chosen_plan": plan.plan.plan_id,
                                "best_plan": best_plan.plan.plan_id,
                                "target_serial": chosen.target_serial,
                                "energy_card_id": chosen.card_id,
                            },
                        )
                    )
                    counts["ENERGY_ATTACH_SUBOPTIMAL"] += 1
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

        trace_codes = _trace_failure_codes(row, next_row, obs)
        if "BAD_SPREAD_TARGET" in trace_codes or "SPREAD_TARGET_REGRET" in trace_codes:
            audit.findings.append(
                _finding(
                    step=step_index,
                    turn=turn,
                    seat=seat,
                    code="SPREAD_TARGET_REGRET",
                    severity="MAJOR",
                    recorded=recorded,
                    expected=None,
                    runner_id="DECK_SPECIFIC_SPREAD_ADAPTER",
                    evidence={"source": "decision_trace"},
                )
            )
            counts["SPREAD_TARGET_REGRET"] += 1

    domains = {
        "runtime": 100.0,
        "terminal": 100.0,
        "promotion": 100.0,
        "energy": 100.0,
        "spread": 100.0,
        "attack": 100.0,
        "clock": 100.0,
        "tempo": 100.0,
    }
    total_penalty = 0.0
    for finding in audit.findings:
        penalty = SEVERITY_PENALTY.get(finding.severity, 0.0)
        total_penalty += penalty
        domain = DOMAIN_BY_CODE.get(finding.code)
        if domain:
            domains[domain] = max(0.0, domains[domain] - penalty)
    audit.domain_scores = domains
    audit.overall_score = max(0.0, 100.0 - total_penalty)
    audit.metadata = {
        "finding_counts": dict(counts),
        "canonical_failure_counts": canonical_failure_counts(finding.code for finding in audit.findings),
        "classifier_support": {
            "LETHAL_MISS": "BUILT_IN",
            "ENERGY_ATTACH_ERROR": "BUILT_IN_ROCKET_MEWTWO",
            "TERMINAL_MISS": "BUILT_IN",
            "PROMOTION_ERROR": "BUILT_IN",
            "BAD_SPREAD_TARGET": "DECK_SPECIFIC_TRACE_REQUIRED",
        },
        "source": str(Path(path)),
    }
    return audit
