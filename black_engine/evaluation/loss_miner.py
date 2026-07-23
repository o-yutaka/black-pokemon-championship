from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from black_engine.championship_policy import ChampionshipRocketMewtwoPolicy
from black_engine.prize_truth import prize_value
from black_engine.rocket_mewtwo_worldline import (
    CTX_SWITCH,
    CTX_TO_ACTIVE,
    T_ATTACK,
    T_END,
    T_ENERGY,
)

from .models import DecisionFinding, EpisodeAudit
from .replay_judge import audit_episode

LOSS_MODES = (
    "MEWTWO_SETUP_DELAY",
    "NO_BACKUP_AFTER_SPIDOPS",
    "UNREADY_EX_EXPOSED",
    "NONPERSISTENT_DAMAGE_LOOP",
    "DECK_OUT_CLOCK",
)

SEVERITY_WEIGHT = {"FATAL": 100, "MAJOR": 25, "MINOR": 5}

FINDING_TO_LOSS_MODE = {
    "ATTACK_WITHOUT_BACKUP": "NO_BACKUP_AFTER_SPIDOPS",
    "PRIZE_AWARE_ACTIVE_MISS": "UNREADY_EX_EXPOSED",
    "PROMOTION_LETHAL_MISS": "UNREADY_EX_EXPOSED",
    "NONPERSISTENT_DAMAGE_REPEAT": "NONPERSISTENT_DAMAGE_LOOP",
    "DECK_CLOCK_VIOLATION": "DECK_OUT_CLOCK",
}

REPAIR_CONTRACTS = {
    "MEWTWO_SETUP_DELAY": {
        "policy_hook": "MEWTWO_SETUP_BEFORE_TURN_CLOSE",
        "acceptance": (
            "When a legal FIRST_MEWTWO_READY or SECOND_MEWTWO_DEVELOPMENT attachment "
            "exists, a nonterminal attack or End cannot close the turn before that attachment."
        ),
    },
    "NO_BACKUP_AFTER_SPIDOPS": {
        "policy_hook": "BACKUP_ATTACKER_CONTRACT",
        "acceptance": (
            "Before a nonterminal Spidops attack into an observed counter-KO, at least one "
            "bench attacker must already be attack-ready or become ready this turn."
        ),
    },
    "UNREADY_EX_EXPOSED": {
        "policy_hook": "FORBID_VOLUNTARY_SWITCH_TO_UNREADY_EX",
        "acceptance": (
            "A one-Prize Active cannot be voluntarily replaced by an unready multi-Prize "
            "Pokemon inside observed lethal damage unless the switch wins immediately."
        ),
    },
    "NONPERSISTENT_DAMAGE_LOOP": {
        "policy_hook": "REJECT_NONPERSISTENT_DAMAGE",
        "acceptance": (
            "After an attack/target pair produces no persistent HP loss across a turn boundary, "
            "the same nonlethal pair cannot be selected again without a material board change."
        ),
    },
    "DECK_OUT_CLOCK": {
        "policy_hook": "DECK_CLOCK_SUPPRESS_RESOURCE",
        "acceptance": (
            "When safe_draw_budget is nonpositive, optional long-horizon search/draw actions "
            "cannot outrank attack, survival, or End routes."
        ),
    },
}


@dataclass(frozen=True)
class LossModeCase:
    episode_id: int | str
    agent_name: str
    loss_mode: str
    detail_code: str
    step: int
    turn: int
    severity: str
    recorded: list[int]
    expected: list[int] | None
    evidence: dict[str, Any]
    policy_hook: str
    acceptance: str
    confidence: float

    @property
    def priority(self) -> int:
        return SEVERITY_WEIGHT.get(self.severity, 0)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["priority"] = self.priority
        return payload


@dataclass(frozen=True)
class LossModeReport:
    episode_id: int | str
    agent_name: str
    result: str
    cases: tuple[LossModeCase, ...]

    def to_dict(self) -> dict[str, Any]:
        counts = Counter(case.loss_mode for case in self.cases)
        return {
            "episode_id": self.episode_id,
            "agent_name": self.agent_name,
            "result": self.result,
            "counts": {mode: counts.get(mode, 0) for mode in LOSS_MODES},
            "priority": sum(case.priority for case in self.cases),
            "cases": [case.to_dict() for case in self.cases],
        }


def _agents(payload: dict) -> list[str]:
    info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
    values = info.get("Agents") if isinstance(info.get("Agents"), list) else []
    return [str(value.get("Name", "")) if isinstance(value, dict) else "" for value in values]


def _finding_case(audit: EpisodeAudit, finding: DecisionFinding) -> LossModeCase | None:
    loss_mode = FINDING_TO_LOSS_MODE.get(finding.code)
    if finding.code == "ENERGY_ATTACH_SUBOPTIMAL":
        best_plan = str(finding.evidence.get("best_plan", ""))
        if best_plan in {"FIRST_MEWTWO_READY", "SECOND_MEWTWO_DEVELOPMENT"}:
            loss_mode = "MEWTWO_SETUP_DELAY"
    if loss_mode is None:
        return None
    contract = REPAIR_CONTRACTS[loss_mode]
    return LossModeCase(
        episode_id=audit.episode_id,
        agent_name=audit.agent_name,
        loss_mode=loss_mode,
        detail_code=finding.code,
        step=finding.step,
        turn=finding.turn,
        severity=finding.severity,
        recorded=list(finding.recorded),
        expected=list(finding.expected) if finding.expected is not None else None,
        evidence={**finding.evidence, "source": "replay_judge"},
        policy_hook=contract["policy_hook"],
        acceptance=contract["acceptance"],
        confidence=1.0,
    )


def _best_setup_attachment(policy: ChampionshipRocketMewtwoPolicy, context: dict):
    truth = context["truth"]
    candidates = []
    for option in truth.options:
        if option.action_type != T_ENERGY:
            continue
        result = policy._plan_for_option(option.action_index, context)
        if result.illegal:
            continue
        if result.plan.plan_id in {"FIRST_MEWTWO_READY", "SECOND_MEWTWO_DEVELOPMENT"}:
            candidates.append(result)
    if not candidates:
        return None
    return policy.judge.choose(candidates)


def _closing_setup_delay_cases(path: Path, agent_name: str, audit: EpisodeAudit) -> list[LossModeCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    agents = _agents(payload)
    if agent_name not in agents:
        return []
    seat = agents.index(agent_name)
    policy = ChampionshipRocketMewtwoPolicy()
    result: list[LossModeCase] = []
    steps = payload.get("steps") if isinstance(payload.get("steps"), list) else []

    for step_index, pair in enumerate(steps[:-1]):
        if not isinstance(pair, list) or seat >= len(pair) or not isinstance(pair[seat], dict):
            continue
        row = pair[seat]
        if row.get("status") != "ACTIVE":
            continue
        obs = row.get("observation") if isinstance(row.get("observation"), dict) else None
        next_pair = steps[step_index + 1]
        next_row = (
            next_pair[seat]
            if isinstance(next_pair, list) and seat < len(next_pair) and isinstance(next_pair[seat], dict)
            else {}
        )
        recorded = next_row.get("action")
        if not isinstance(obs, dict) or not isinstance(obs.get("select"), dict):
            continue
        options = obs["select"].get("option") if isinstance(obs["select"].get("option"), list) else []
        if not options or not isinstance(recorded, list) or len(recorded) != 1:
            continue

        context = policy.build_context(obs)
        truth = context["truth"]
        if context.get("ready_mewtwo"):
            continue
        actual = recorded[0]
        if not (0 <= actual < len(truth.options)):
            continue
        chosen = truth.options[actual]
        if chosen.action_type not in {T_ATTACK, T_END}:
            continue

        setup = _best_setup_attachment(policy, context)
        if setup is None or setup.plan.root_action_index == actual:
            continue
        terminal = policy._terminal_attack(context)
        if terminal is not None and terminal == actual:
            continue

        immediate_ko = False
        if chosen.action_type == T_ATTACK:
            target = truth.opponent_active
            immediate_ko = bool(
                target
                and policy._attack_option_damage(chosen, context) >= target.current_hp > 0
            )

        current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
        turn = int(current.get("turn", 0) or 0)
        contract = REPAIR_CONTRACTS["MEWTWO_SETUP_DELAY"]
        result.append(
            LossModeCase(
                episode_id=audit.episode_id,
                agent_name=agent_name,
                loss_mode="MEWTWO_SETUP_DELAY",
                detail_code="MEWTWO_SETUP_TURN_CLOSED",
                step=step_index,
                turn=turn,
                severity="MAJOR",
                recorded=list(recorded),
                expected=[setup.plan.root_action_index],
                evidence={
                    "source": "official_legal_options",
                    "chosen_action_type": chosen.action_type,
                    "chosen_attack_immediate_ko": immediate_ko,
                    "best_setup_plan": setup.plan.plan_id,
                    "best_setup_index": setup.plan.root_action_index,
                    "ready_mewtwo": 0,
                    "backup_attacker_ready": bool(context.get("backup_attacker_ready")),
                },
                policy_hook=contract["policy_hook"],
                acceptance=contract["acceptance"],
                confidence=0.98,
            )
        )
    return result


def _scan_observed_attack_damage(logs: Any, seat: int, known: dict[int, int]) -> None:
    if not isinstance(logs, list):
        return
    opponent = 1 - seat
    last_attacker_card: int | None = None
    for value in logs:
        if not isinstance(value, dict):
            continue
        if value.get("type") == 15 and value.get("playerIndex") == opponent:
            card = value.get("cardId")
            last_attacker_card = card if type(card) is int else None
            continue
        if (
            value.get("type") == 16
            and value.get("playerIndex") == seat
            and value.get("putDamageCounter") is False
            and last_attacker_card is not None
        ):
            raw = value.get("value")
            if type(raw) in (int, float):
                damage = abs(int(raw))
                known[last_attacker_card] = max(damage, known.get(last_attacker_card, 0))


def _unready_ex_exposure_cases(path: Path, agent_name: str, audit: EpisodeAudit) -> list[LossModeCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    agents = _agents(payload)
    if agent_name not in agents:
        return []
    seat = agents.index(agent_name)
    policy = ChampionshipRocketMewtwoPolicy()
    known_damage: dict[int, int] = {}
    cases: list[LossModeCase] = []
    steps = payload.get("steps") if isinstance(payload.get("steps"), list) else []

    for step_index, pair in enumerate(steps[:-1]):
        if not isinstance(pair, list) or seat >= len(pair) or not isinstance(pair[seat], dict):
            continue
        row = pair[seat]
        obs = row.get("observation") if isinstance(row.get("observation"), dict) else None
        if not isinstance(obs, dict):
            continue
        _scan_observed_attack_damage(obs.get("logs"), seat, known_damage)
        if row.get("status") != "ACTIVE" or not isinstance(obs.get("select"), dict):
            continue
        next_pair = steps[step_index + 1]
        next_row = (
            next_pair[seat]
            if isinstance(next_pair, list) and seat < len(next_pair) and isinstance(next_pair[seat], dict)
            else {}
        )
        recorded = next_row.get("action")
        if not isinstance(recorded, list) or len(recorded) != 1:
            continue

        select = obs["select"]
        context_id = int(select.get("context", -1) or -1)
        if context_id not in {CTX_SWITCH, CTX_TO_ACTIVE}:
            continue

        current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
        players = current.get("players") if isinstance(current.get("players"), list) else []
        their_active = []
        if 0 <= 1 - seat < len(players) and isinstance(players[1 - seat], dict):
            their_active = players[1 - seat].get("active") or []
        attacker_card = None
        if their_active and isinstance(their_active[0], dict) and type(their_active[0].get("id")) is int:
            attacker_card = their_active[0]["id"]
        observed = known_damage.get(attacker_card, 0) if attacker_card is not None else 0
        if observed <= 0:
            continue

        if attacker_card is not None:
            policy.observed_damage_by_attacker[attacker_card] = observed
        context = policy.build_context(obs)
        truth = context["truth"]
        actual = recorded[0]
        if not (0 <= actual < len(truth.options)):
            continue
        current_active = truth.active
        candidate = policy._promotion_candidate(truth.options[actual], context)
        if current_active is None or candidate is None:
            continue
        if prize_value(current_active.card_id) != 1 or prize_value(candidate.card_id) <= 1:
            continue
        if policy._pokemon_attack_ready(candidate, context):
            continue
        if observed < candidate.current_hp:
            continue

        expected = policy._promotion_choice(context)
        terminal_loss = truth.opponent_prizes > 0 and prize_value(candidate.card_id) >= truth.opponent_prizes
        contract = REPAIR_CONTRACTS["UNREADY_EX_EXPOSED"]
        cases.append(
            LossModeCase(
                episode_id=audit.episode_id,
                agent_name=agent_name,
                loss_mode="UNREADY_EX_EXPOSED",
                detail_code="KNOWN_LETHAL_UNREADY_EX_SWITCH",
                step=step_index,
                turn=int(current.get("turn", 0) or 0),
                severity="FATAL" if terminal_loss else "MAJOR",
                recorded=list(recorded),
                expected=[expected] if expected is not None and expected != actual else None,
                evidence={
                    "source": "official_attack_and_damage_logs",
                    "opponent_attacker_card_id": attacker_card,
                    "observed_damage": observed,
                    "current_active_card_id": current_active.card_id,
                    "current_active_prize_value": prize_value(current_active.card_id),
                    "candidate_card_id": candidate.card_id,
                    "candidate_hp": candidate.current_hp,
                    "candidate_prize_value": prize_value(candidate.card_id),
                    "candidate_attack_ready": False,
                    "opponent_remaining_prizes": truth.opponent_prizes,
                    "terminal_loss": terminal_loss,
                },
                policy_hook=contract["policy_hook"],
                acceptance=contract["acceptance"],
                confidence=1.0,
            )
        )
    return cases


def mine_episode(path: str | Path, agent_name: str) -> LossModeReport:
    replay = Path(path)
    audit = audit_episode(replay, agent_name)
    cases = [case for finding in audit.findings if (case := _finding_case(audit, finding)) is not None]
    cases.extend(_closing_setup_delay_cases(replay, agent_name, audit))
    cases.extend(_unready_ex_exposure_cases(replay, agent_name, audit))

    unique: dict[tuple[int, str], LossModeCase] = {}
    for case in cases:
        key = (case.step, case.loss_mode)
        existing = unique.get(key)
        if existing is None or case.priority > existing.priority or case.confidence > existing.confidence:
            unique[key] = case
    ordered = tuple(sorted(unique.values(), key=lambda case: (-case.priority, case.step, case.loss_mode)))
    return LossModeReport(audit.episode_id, agent_name, audit.result, ordered)


def aggregate_reports(reports: Iterable[LossModeReport]) -> dict[str, Any]:
    values = list(reports)
    counts: Counter[str] = Counter()
    priority: Counter[str] = Counter()
    episodes: dict[str, set[str]] = {mode: set() for mode in LOSS_MODES}
    examples: dict[str, list[dict[str, Any]]] = {mode: [] for mode in LOSS_MODES}

    for report in values:
        for case in report.cases:
            counts[case.loss_mode] += 1
            priority[case.loss_mode] += case.priority
            episodes[case.loss_mode].add(str(case.episode_id))
            if len(examples[case.loss_mode]) < 5:
                examples[case.loss_mode].append(case.to_dict())

    queue = []
    for mode in LOSS_MODES:
        contract = REPAIR_CONTRACTS[mode]
        queue.append(
            {
                "loss_mode": mode,
                "count": counts.get(mode, 0),
                "priority": priority.get(mode, 0),
                "episodes": sorted(episodes[mode]),
                "policy_hook": contract["policy_hook"],
                "acceptance": contract["acceptance"],
                "examples": examples[mode],
            }
        )
    queue.sort(key=lambda item: (-item["priority"], -item["count"], item["loss_mode"]))
    return {
        "episodes": len(values),
        "losses": sum(report.result == "LOSS" for report in values),
        "wins": sum(report.result == "WIN" for report in values),
        "total_cases": sum(counts.values()),
        "counts": {mode: counts.get(mode, 0) for mode in LOSS_MODES},
        "repair_queue": queue,
    }
