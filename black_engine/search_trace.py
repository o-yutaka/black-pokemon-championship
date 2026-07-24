from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import random
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

ACTION_ATTACK = 13


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _integer(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _card_id(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value if value >= 0 else None
    if isinstance(value, Mapping):
        for key in ("id", "cardId", "card", "pokemonId"):
            raw = value.get(key)
            if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
                return raw
    return None


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def _collect_card_ids(value: Any) -> list[int]:
    result: list[int] = []
    if isinstance(value, Mapping):
        cid = _card_id(value)
        if cid is not None:
            result.append(cid)
        for key in ("preEvolution", "evolution", "energyCards", "energies", "tools", "toolCards", "attached"):
            if key in value:
                result.extend(_collect_card_ids(value[key]))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            result.extend(_collect_card_ids(item))
    return result


def _player(current: Mapping[str, Any], index: int) -> dict[str, Any]:
    players = _sequence(current.get("players"))
    return _mapping(players[index]) if 0 <= index < len(players) else {}


def _visible_ids(player: Mapping[str, Any], *, include_hand: bool) -> list[int]:
    result: list[int] = []
    for key in ("active", "bench", "discard", "lostZone", "looking"):
        result.extend(_collect_card_ids(player.get(key)))
    if include_hand:
        result.extend(_collect_card_ids(player.get("hand")))
    return result


def _remaining_cards(deck: Sequence[int], known: Sequence[int]) -> list[int] | None:
    counts = Counter(int(card) for card in deck)
    for card in known:
        counts[int(card)] -= 1
        if counts[int(card)] < 0:
            return None
    result: list[int] = []
    for card, count in sorted(counts.items()):
        result.extend([card] * count)
    return result


def _zone_count(player: Mapping[str, Any], key: str) -> int:
    direct = player.get(f"{key}Count")
    if isinstance(direct, (int, float)) and not isinstance(direct, bool):
        return max(0, int(direct))
    return len(_sequence(player.get(key)))


def _public_card(card: Any) -> dict[str, Any] | None:
    if not isinstance(card, Mapping):
        return None
    return {
        "id": _card_id(card),
        "serial": card.get("serial", card.get("instanceSerial")),
        "hp": card.get("hp", card.get("currentHp")),
        "maxHp": card.get("maxHp", card.get("maxHP")),
        "energy": len(_sequence(card.get("energyCards", card.get("energies")))),
        "status": _sequence(card.get("status", card.get("statuses"))),
    }


def _public_board(player: Mapping[str, Any]) -> dict[str, Any]:
    active = _sequence(player.get("active", player.get("activePokemon")))
    bench = _sequence(player.get("bench", player.get("benchPokemon")))
    return {
        "active": _public_card(active[0]) if active else None,
        "bench": [_public_card(card) for card in bench],
    }


def _damage_on(player: Mapping[str, Any]) -> int:
    total = 0
    for card in [*_sequence(player.get("active")), *_sequence(player.get("bench"))]:
        if not isinstance(card, Mapping):
            continue
        maximum = _integer(card.get("maxHp", card.get("maxHP")), 0)
        hp = _integer(card.get("hp", card.get("currentHp", maximum)), maximum)
        total += max(0, maximum - hp)
    return total


def _energy_on(player: Mapping[str, Any]) -> int:
    return sum(len(_sequence(card.get("energyCards", card.get("energies")))) for card in [*_sequence(player.get("active")), *_sequence(player.get("bench"))] if isinstance(card, Mapping))


def state_summary(observation: Mapping[str, Any], actor: int) -> dict[str, Any]:
    current = _mapping(observation.get("current"))
    me = _player(current, actor)
    opponent = _player(current, 1 - actor)
    options = _sequence(_mapping(observation.get("select")).get("option"))
    attack_ready = any(_integer(_mapping(option).get("type"), -1) == ACTION_ATTACK for option in options)
    board = {"me": _public_board(me), "opponent": _public_board(opponent)}
    position = {
        "me": {"active": [(card or {}).get("id") for card in [board["me"]["active"]] if card], "bench": [(card or {}).get("id") for card in board["me"]["bench"] if card]},
        "opponent": {"active": [(card or {}).get("id") for card in [board["opponent"]["active"]] if card], "bench": [(card or {}).get("id") for card in board["opponent"]["bench"] if card]},
    }
    result = current.get("result", observation.get("result", -1))
    return {
        "stateHash": _stable_hash({"current": current, "select": observation.get("select")}),
        "boardHash": _stable_hash(board),
        "positionHash": _stable_hash(position),
        "turn": _integer(current.get("turn", observation.get("turn")), 0),
        "actingPlayer": _integer(current.get("yourIndex", observation.get("playerIndex")), actor),
        "handCount": _zone_count(me, "hand"),
        "deckCount": _zone_count(me, "deck"),
        "prizeCount": _zone_count(me, "prize"),
        "opponentPrizeCount": _zone_count(opponent, "prize"),
        "energyCount": _energy_on(me),
        "damageOnOpponent": _damage_on(opponent),
        "attackReady": attack_ready,
        "retreated": bool(me.get("retreated", me.get("retreatUsed", False))),
        "result": result if isinstance(result, int) else -1,
        "board": board,
    }


def compare_prediction(predicted: Mapping[str, Any] | None, actual_observation: Mapping[str, Any], actor: int) -> dict[str, Any] | None:
    if not predicted:
        return None
    actual = state_summary(actual_observation, actor)
    fields = ("boardHash", "prizeCount", "energyCount", "damageOnOpponent", "attackReady")
    mismatch = [field for field in fields if predicted.get(field) != actual.get(field)]
    return {
        "source": "official_search_prediction_vs_next_observation",
        "predictedDecisionId": predicted.get("decisionId"),
        "predicted": {field: predicted.get(field) for field in fields},
        "actual": {field: actual.get(field) for field in fields},
        "mismatch": mismatch,
        "matched": not mismatch,
    }


def _state_parts(state: Any) -> tuple[int, dict[str, Any], int]:
    raw = _mapping(state)
    search_id = next((_integer(raw.get(key), -1) for key in ("searchId", "search_id", "id") if raw.get(key) is not None), -1)
    observation: dict[str, Any] = {}
    for key in ("observation", "obs", "agentObservation", "agent_observation"):
        candidate = raw.get(key)
        if isinstance(candidate, Mapping):
            observation = dict(candidate)
            break
        converted = _mapping(candidate)
        if converted:
            observation = converted
            break
    if not observation and "current" in raw:
        observation = raw
    result = next((_integer(raw.get(key), -1) for key in ("result", "winner") if raw.get(key) is not None), -1)
    if result == -1:
        result = _integer(_mapping(observation.get("current")).get("result"), -1)
    if search_id < 0 or not observation:
        raise RuntimeError(f"invalid SearchState keys={sorted(raw)}")
    return search_id, observation, result


def _option_label(index: int, option: Any) -> str:
    raw = _mapping(option)
    action_type = raw.get("type", raw.get("actionType", "ACTION"))
    cid = _card_id(raw)
    attack = raw.get("attackId")
    target = raw.get("inPlayIndex", raw.get("index"))
    parts = [f"[{index}]", str(action_type)]
    if cid is not None:
        parts.append(f"card#{cid}")
    if isinstance(attack, int):
        parts.append(f"attack#{attack}")
    if isinstance(target, int):
        parts.append(f"target={target}")
    return " · ".join(parts)


def _reward(before: Mapping[str, Any], after: Mapping[str, Any], actor: int) -> float:
    result = _integer(after.get("result"), -1)
    if result in (0, 1):
        return 1.0 if result == actor else -1.0
    prize_gain = _integer(before.get("prizeCount")) - _integer(after.get("prizeCount"))
    damage_gain = _integer(after.get("damageOnOpponent")) - _integer(before.get("damageOnOpponent"))
    energy_gain = _integer(after.get("energyCount")) - _integer(before.get("energyCount"))
    hand_delta = _integer(after.get("handCount")) - _integer(before.get("handCount"))
    value = 0.42 * prize_gain + 0.0025 * damage_gain + 0.06 * energy_gain + 0.14 * int(bool(after.get("attackReady"))) + 0.015 * hand_delta
    return max(-1.0, min(1.0, value))


def _cycle_evidence(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any] | None:
    same_board = before.get("positionHash") == after.get("positionHash")
    attack_delta = int(bool(after.get("attackReady"))) - int(bool(before.get("attackReady")))
    prize_delta = _integer(before.get("prizeCount")) - _integer(after.get("prizeCount"))
    energy_delta = _integer(after.get("energyCount")) - _integer(before.get("energyCount"))
    damage_delta = _integer(after.get("damageOnOpponent")) - _integer(before.get("damageOnOpponent"))
    retreat_used = bool(after.get("retreated")) and not bool(before.get("retreated"))
    if same_board and attack_delta <= 0 and prize_delta <= 0 and damage_delta <= 0 and (energy_delta < 0 or retreat_used):
        return {
            "state_before": before.get("stateHash"),
            "state_after": after.get("stateHash"),
            "same_active_and_bench": True,
            "attack_delta": attack_delta,
            "prize_delta": prize_delta,
            "damage_delta": damage_delta,
            "energy_delta": energy_delta,
            "retreat_used": retreat_used,
        }
    return None


class LocalSearchTracer:
    """Trace-only root search using the documented cg.api Search API.

    It never changes the submitted action. Search is enabled only when the local
    Battle Studio passes both complete deck lists through configuration.
    """

    def __init__(self, api: Any | None = None) -> None:
        self._api = api

    def _load_api(self) -> Any:
        api = self._api or importlib.import_module("cg.api")
        missing = [name for name in ("search_begin", "search_step", "search_release", "search_end") if not callable(getattr(api, name, None))]
        if missing:
            raise RuntimeError(f"cg.api Search API missing: {missing}")
        return api

    @staticmethod
    def _trace_config(configuration: Any) -> dict[str, Any]:
        if not isinstance(configuration, Mapping):
            return {}
        raw = configuration.get("blackDecisionTrace")
        return dict(raw) if isinstance(raw, Mapping) else {}

    @staticmethod
    def _determinize(obs: Mapping[str, Any], actor: int, your_deck: Sequence[int], opponent_deck: Sequence[int], seed: int) -> dict[str, list[int]]:
        current = _mapping(obs.get("current"))
        mine = _player(current, actor)
        theirs = _player(current, 1 - actor)
        own_remaining = _remaining_cards(your_deck, _visible_ids(mine, include_hand=True))
        opponent_remaining = _remaining_cards(opponent_deck, _visible_ids(theirs, include_hand=False))
        if own_remaining is None or opponent_remaining is None:
            raise RuntimeError("visible cards are not a subset of supplied deck lists")

        own_deck_count = _zone_count(mine, "deck")
        own_prize_count = _zone_count(mine, "prize")
        opponent_deck_count = _zone_count(theirs, "deck")
        opponent_prize_count = _zone_count(theirs, "prize")
        visible_opponent_hand = len(_collect_card_ids(theirs.get("hand")))
        opponent_hand_count = max(0, _zone_count(theirs, "hand") - visible_opponent_hand)
        if len(own_remaining) != own_deck_count + own_prize_count:
            raise RuntimeError(f"own hidden-zone mismatch remaining={len(own_remaining)} expected={own_deck_count + own_prize_count}")
        expected_opponent = opponent_deck_count + opponent_prize_count + opponent_hand_count
        if len(opponent_remaining) != expected_opponent:
            raise RuntimeError(f"opponent hidden-zone mismatch remaining={len(opponent_remaining)} expected={expected_opponent}")

        rng = random.Random(seed)
        rng.shuffle(own_remaining)
        rng.shuffle(opponent_remaining)
        own_prize = own_remaining[:own_prize_count]
        own_deck = own_remaining[own_prize_count:]
        opponent_hand = opponent_remaining[:opponent_hand_count]
        opponent_prize = opponent_remaining[opponent_hand_count:opponent_hand_count + opponent_prize_count]
        opponent_hidden_deck = opponent_remaining[opponent_hand_count + opponent_prize_count:]
        opponent_active = _collect_card_ids(theirs.get("active"))
        return {
            "yourDeck": own_deck,
            "yourPrize": own_prize,
            "opponentDeck": opponent_hidden_deck,
            "opponentPrize": opponent_prize,
            "opponentHand": opponent_hand,
            "opponentActive": opponent_active,
        }

    def evaluate(self, obs: Mapping[str, Any], configuration: Any, your_deck: Sequence[int], selection: Sequence[int]) -> dict[str, Any]:
        config = self._trace_config(configuration)
        options = _sequence(_mapping(obs.get("select")).get("option"))
        actor = _integer(_mapping(obs.get("current")).get("yourIndex"), _integer(config.get("playerIndex"), 0))
        base = state_summary(obs, actor)
        disabled = {
            "enabled": False,
            "reason": "local trace configuration not supplied",
            "source": "none",
            "searchTree": {"id": "root", "label": "Root", "status": "unavailable", "children": []},
            "rejectedBranches": [],
            "counterfactuals": [],
            "selectedPrediction": None,
            "hiddenBelief": {},
        }
        if not config.get("enabled"):
            return disabled
        opponent_deck = config.get("opponentDeck")
        if not isinstance(opponent_deck, Sequence) or isinstance(opponent_deck, (str, bytes, bytearray)):
            return {**disabled, "reason": "opponent deck unavailable"}
        select = _mapping(obs.get("select"))
        minimum = _integer(select.get("minCount"), 0)
        maximum_raw = select.get("maxCount", minimum)
        maximum = minimum if maximum_raw is None else _integer(maximum_raw, minimum)
        if minimum != 1 or maximum != 1 or not options:
            return {**disabled, "reason": "root Search trace supports single-select decisions only"}

        simulations = max(1, min(8, _integer(config.get("simulationsPerAction"), 2)))
        budget_ms = max(5.0, min(250.0, float(config.get("budgetMs", 45.0))))
        started = time.perf_counter()
        stats: dict[int, list[tuple[float, dict[str, Any], dict[str, Any] | None]]] = {index: [] for index in range(len(options))}
        errors: list[str] = []
        api = None
        seed_base = int(_stable_hash({"state": base["stateHash"], "deck": list(your_deck), "opponent": list(opponent_deck)}), 16)
        try:
            api = self._load_api()
            converter = getattr(api, "to_observation_class", None)
            for simulation in range(simulations):
                hidden = self._determinize(obs, actor, your_deck, [int(card) for card in opponent_deck], seed_base + simulation)
                for index in range(len(options)):
                    if (time.perf_counter() - started) * 1000.0 >= budget_ms:
                        break
                    root_id = child_id = None
                    try:
                        observation_arg: Any = dict(obs)
                        if callable(converter):
                            observation_arg = converter(observation_arg)
                        root_state = api.search_begin(
                            observation_arg,
                            hidden["yourDeck"],
                            hidden["yourPrize"],
                            hidden["opponentDeck"],
                            hidden["opponentPrize"],
                            hidden["opponentHand"],
                            hidden["opponentActive"],
                            False,
                        )
                        root_id, _, _ = _state_parts(root_state)
                        child_state = api.search_step(root_id, [index])
                        child_id, child_obs, _ = _state_parts(child_state)
                        after = state_summary(child_obs, actor)
                        stats[index].append((_reward(base, after, actor), after, _cycle_evidence(base, after)))
                    except Exception as exc:
                        errors.append(f"option={index} {type(exc).__name__}: {exc}")
                    finally:
                        for search_id in (child_id, root_id):
                            if isinstance(search_id, int) and search_id >= 0:
                                try:
                                    api.search_release(search_id)
                                except Exception:
                                    pass
                if (time.perf_counter() - started) * 1000.0 >= budget_ms:
                    break
        except Exception as exc:
            return {**disabled, "reason": f"{type(exc).__name__}: {exc}", "errors": [str(exc)]}
        finally:
            if api is not None:
                try:
                    api.search_end()
                except Exception:
                    pass

        selected = selection[0] if len(selection) == 1 and isinstance(selection[0], int) else -1
        nodes: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        counterfactuals: list[dict[str, Any]] = []
        selected_prediction: dict[str, Any] | None = None
        selected_mean: float | None = None
        for index, option in enumerate(options):
            samples = stats[index]
            values = [sample[0] for sample in samples]
            mean = sum(values) / len(values) if values else None
            status = "selected" if index == selected else "expanded" if samples else "unavailable"
            node = {
                "id": f"root:{index}",
                "label": _option_label(index, option),
                "status": status,
                "ev": None if mean is None else mean * 100.0,
                "visits": len(values),
                "mean": mean,
                "worst": min(values) if values else None,
                "best": max(values) if values else None,
                "selected": index == selected,
                "pruned": False,
                "children": [],
                "source": "cg.api.search_begin/search_step",
            }
            nodes.append(node)
            cycle = next((sample[2] for sample in samples if sample[2]), None)
            if cycle is not None:
                node["pruned"] = index != selected
                node["status"] = "selected_cycle_warning" if index == selected else "pruned"
                rejected.append({
                    "action": node["label"],
                    "optionIndex": index,
                    "reason": "RESOURCE_LOSS_CYCLE",
                    "evidence": cycle,
                    "metrics": {
                        "energy": cycle["energy_delta"],
                        "tempo": cycle["attack_delta"],
                        "prize": cycle["prize_delta"],
                        "damage": cycle["damage_delta"],
                    },
                    "killedBy": "OfficialSearchCycleGuard",
                    "source": "cg.api.search_step",
                })
            if index == selected and samples:
                selected_mean = mean
                selected_prediction = dict(samples[0][1])
            if samples:
                counterfactuals.append({
                    "action": node["label"],
                    "optionIndex": index,
                    "expectedValue": mean,
                    "visits": len(values),
                    "selected": index == selected,
                    "source": "cg.api.search_step + search_state_heuristic",
                })
        if selected_mean is not None:
            for row in counterfactuals:
                value = row.get("expectedValue")
                row["deltaFromSelected"] = None if value is None else value - selected_mean
        if selected_prediction is not None:
            selected_prediction["decisionId"] = None

        completed = sum(len(samples) for samples in stats.values())
        reason = "" if completed else (errors[0] if errors else "Search API produced no child states")
        return {
            "enabled": completed > 0,
            "reason": reason,
            "source": "cg.api Search API",
            "elapsedMs": (time.perf_counter() - started) * 1000.0,
            "simulations": completed,
            "searchTree": {
                "id": "root",
                "label": "Root",
                "status": "expanded" if completed else "unavailable",
                "visits": completed,
                "children": nodes,
                "source": "cg.api.search_begin/search_step",
            },
            "rejectedBranches": rejected,
            "counterfactuals": counterfactuals,
            "selectedPrediction": selected_prediction,
            "hiddenBelief": {
                "source": "determinized from both uploaded deck lists",
                "samples": min(simulations, max((len(samples) for samples in stats.values()), default=0)),
                "opponentDeckSize": len(opponent_deck),
                "truthBoundary": "hidden cards are sampled for Search only; not treated as observed truth",
            },
            "errors": errors[:10],
        }
