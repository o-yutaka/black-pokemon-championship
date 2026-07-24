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
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:20]


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


def _zone_count(player: Mapping[str, Any], key: str) -> int:
    direct = player.get(f"{key}Count")
    if isinstance(direct, (int, float)) and not isinstance(direct, bool):
        return max(0, int(direct))
    return len(_sequence(player.get(key)))


def _remaining(deck: Sequence[int], known: Sequence[int]) -> list[int]:
    counts = Counter(int(card) for card in deck)
    for card in known:
        counts[int(card)] -= 1
        if counts[int(card)] < 0:
            raise ValueError(f"visible card count exceeds supplied deck: card_id={card}")
    result: list[int] = []
    for card, count in sorted(counts.items()):
        result.extend([card] * count)
    return result


def _sample(values: list[int], count: int, rng: random.Random) -> tuple[list[int], list[int]]:
    if count < 0 or count > len(values):
        raise ValueError(f"cannot sample count={count} from {len(values)} cards")
    pool = list(values)
    rng.shuffle(pool)
    return pool[:count], pool[count:]


def _sample_specific(values: list[int], candidates: set[int] | None, count: int, rng: random.Random) -> tuple[list[int], list[int]]:
    if count <= 0:
        return [], list(values)
    pool = [card for card in values if candidates is None or card in candidates]
    if len(pool) < count:
        raise ValueError(f"not enough valid Pokemon for opaque Active: need={count} available={len(pool)}")
    rng.shuffle(pool)
    selected = pool[:count]
    remaining = list(values)
    for card in selected:
        remaining.remove(card)
    return selected, remaining


def _opaque_slots(player: Mapping[str, Any]) -> tuple[int, int]:
    active = _sequence(player.get("active"))
    bench = _sequence(player.get("bench"))
    return sum(item is None for item in active), sum(item is None for item in bench)


def _public_in_play_ids(player: Mapping[str, Any]) -> list[int]:
    return _collect_card_ids([*_sequence(player.get("active")), *_sequence(player.get("bench"))])


def _extras(observation: Mapping[str, Any], player_index: int) -> list[int]:
    current = _mapping(observation.get("current"))
    result: list[int] = []
    for key in ("stadium", "looking"):
        raw = current.get(key)
        entries = _sequence(raw) if not isinstance(raw, Mapping) else [raw]
        for entry in entries:
            if isinstance(entry, Mapping) and _integer(entry.get("playerIndex"), -1) == player_index:
                cid = _card_id(entry)
                if cid is not None:
                    result.append(cid)
    effect = _mapping(_mapping(observation.get("select")).get("effect"))
    if effect and _integer(effect.get("playerIndex"), -1) == player_index:
        effect_serial = effect.get("serial", effect.get("instanceSerial"))
        in_play_serials = {
            card.get("serial", card.get("instanceSerial"))
            for card in [*_sequence(_player(current, player_index).get("active")), *_sequence(_player(current, player_index).get("bench"))]
            if isinstance(card, Mapping)
        }
        if effect_serial not in in_play_serials:
            cid = _card_id(effect)
            if cid is not None:
                result.append(cid)
    return result


def _known_prize(player: Mapping[str, Any]) -> tuple[list[int], int]:
    prize = _sequence(player.get("prize"))
    count = _zone_count(player, "prize")
    if not prize:
        return [], count
    known = [cid for item in prize if (cid := _card_id(item)) is not None]
    return known, max(0, count - len(known))


def _pokemon_ids(api: Any) -> set[int] | None:
    getter = getattr(api, "all_card_data", None)
    if not callable(getter):
        return None
    try:
        return {int(card.cardId) for card in getter() if int(card.cardType) == 0}
    except Exception:
        return None


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


def _board(player: Mapping[str, Any]) -> dict[str, Any]:
    active = _sequence(player.get("active"))
    bench = _sequence(player.get("bench"))
    return {"active": _public_card(active[0]) if active else None, "bench": [_public_card(card) for card in bench]}


def _damage(player: Mapping[str, Any]) -> int:
    total = 0
    for card in [*_sequence(player.get("active")), *_sequence(player.get("bench"))]:
        if isinstance(card, Mapping):
            maximum = _integer(card.get("maxHp", card.get("maxHP")), 0)
            hp = _integer(card.get("hp", card.get("currentHp", maximum)), maximum)
            total += max(0, maximum - hp)
    return total


def _energy(player: Mapping[str, Any]) -> int:
    return sum(len(_sequence(card.get("energyCards", card.get("energies")))) for card in [*_sequence(player.get("active")), *_sequence(player.get("bench"))] if isinstance(card, Mapping))


def state_summary(observation: Mapping[str, Any], actor: int) -> dict[str, Any]:
    current = _mapping(observation.get("current"))
    me, opponent = _player(current, actor), _player(current, 1 - actor)
    options = _sequence(_mapping(observation.get("select")).get("option"))
    board = {"me": _board(me), "opponent": _board(opponent)}
    position = {
        side: {
            "active": [(card or {}).get("id") for card in [value["active"]] if card],
            "bench": [(card or {}).get("id") for card in value["bench"] if card],
        }
        for side, value in board.items()
    }
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
        "energyCount": _energy(me),
        "damageOnOpponent": _damage(opponent),
        "attackReady": any(_integer(_mapping(option).get("type"), -1) == ACTION_ATTACK for option in options),
        "retreated": bool(me.get("retreated", me.get("retreatUsed", False))),
        "result": _integer(current.get("result", observation.get("result")), -1),
        "board": board,
    }


def compare_prediction(predicted: Mapping[str, Any] | None, observation: Mapping[str, Any], actor: int) -> dict[str, Any] | None:
    if not predicted:
        return None
    actual = state_summary(observation, actor)
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
        observation = _mapping(raw.get(key))
        if observation:
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
    parts = [f"[{index}]", str(raw.get("type", raw.get("actionType", "ACTION")))]
    if (cid := _card_id(raw)) is not None:
        parts.append(f"card#{cid}")
    if isinstance(raw.get("attackId"), int):
        parts.append(f"attack#{raw['attackId']}")
    if isinstance(raw.get("inPlayIndex", raw.get("index")), int):
        parts.append(f"target={raw.get('inPlayIndex', raw.get('index'))}")
    return " · ".join(parts)


def _reward(before: Mapping[str, Any], after: Mapping[str, Any], actor: int) -> float:
    result = _integer(after.get("result"), -1)
    if result in (0, 1):
        return 1.0 if result == actor else -1.0
    value = (
        0.42 * (_integer(before.get("prizeCount")) - _integer(after.get("prizeCount")))
        + 0.0025 * (_integer(after.get("damageOnOpponent")) - _integer(before.get("damageOnOpponent")))
        + 0.06 * (_integer(after.get("energyCount")) - _integer(before.get("energyCount")))
        + 0.14 * int(bool(after.get("attackReady")))
        + 0.015 * (_integer(after.get("handCount")) - _integer(before.get("handCount")))
    )
    return max(-1.0, min(1.0, value))


def _cycle(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any] | None:
    attack_delta = int(bool(after.get("attackReady"))) - int(bool(before.get("attackReady")))
    prize_delta = _integer(before.get("prizeCount")) - _integer(after.get("prizeCount"))
    energy_delta = _integer(after.get("energyCount")) - _integer(before.get("energyCount"))
    damage_delta = _integer(after.get("damageOnOpponent")) - _integer(before.get("damageOnOpponent"))
    retreat_used = bool(after.get("retreated")) and not bool(before.get("retreated"))
    if before.get("positionHash") == after.get("positionHash") and attack_delta <= 0 and prize_delta <= 0 and damage_delta <= 0 and (energy_delta < 0 or retreat_used):
        return {
            "state_before": before.get("stateHash"), "state_after": after.get("stateHash"),
            "same_active_and_bench": True, "attack_delta": attack_delta, "prize_delta": prize_delta,
            "damage_delta": damage_delta, "energy_delta": energy_delta, "retreat_used": retreat_used,
        }
    return None


class LocalSearchTracer:
    """Official Search API evidence lane. It never changes the selected action."""

    def __init__(self, api: Any | None = None) -> None:
        self._api = api

    def _load_api(self) -> Any:
        api = self._api or importlib.import_module("cg.api")
        missing = [name for name in ("search_begin", "search_step", "search_release", "search_end") if not callable(getattr(api, name, None))]
        if missing:
            raise RuntimeError(f"cg.api Search API missing: {missing}")
        return api

    @staticmethod
    def _config(configuration: Any) -> dict[str, Any]:
        raw = configuration.get("blackDecisionTrace") if isinstance(configuration, Mapping) else None
        return dict(raw) if isinstance(raw, Mapping) else {}

    @staticmethod
    def _determinize(api: Any, observation: Mapping[str, Any], actor: int, own_deck: Sequence[int], opponent_deck: Sequence[int], seed: int) -> dict[str, list[int]]:
        current = _mapping(observation.get("current"))
        mine, theirs = _player(current, actor), _player(current, 1 - actor)
        rng = random.Random(seed)
        pokemon_ids = _pokemon_ids(api)

        own_known = _public_in_play_ids(mine) + _collect_card_ids(mine.get("hand")) + _collect_card_ids(mine.get("discard")) + _collect_card_ids(mine.get("lostZone")) + _extras(observation, actor)
        own_prize_known, own_prize_unknown = _known_prize(mine)
        own_remaining = _remaining(own_deck, own_known + own_prize_known)
        own_active_nulls, own_bench_nulls = _opaque_slots(mine)
        _, own_remaining = _sample(own_remaining, own_active_nulls + own_bench_nulls, rng)
        sampled_own_prize, own_remaining = _sample(own_remaining, own_prize_unknown, rng)
        full_own_prize = own_prize_known + sampled_own_prize
        if len(own_remaining) != _zone_count(mine, "deck"):
            raise ValueError(f"own hidden-zone mismatch deck={len(own_remaining)} expected={_zone_count(mine, 'deck')}")

        known_opponent_hand = _collect_card_ids(theirs.get("hand"))
        opponent_known = _public_in_play_ids(theirs) + known_opponent_hand + _collect_card_ids(theirs.get("discard")) + _collect_card_ids(theirs.get("lostZone")) + _extras(observation, 1 - actor)
        opponent_prize_known, opponent_prize_unknown = _known_prize(theirs)
        opponent_remaining = _remaining(opponent_deck, opponent_known + opponent_prize_known)
        opponent_active_nulls, opponent_bench_nulls = _opaque_slots(theirs)
        sampled_active, opponent_remaining = _sample_specific(opponent_remaining, pokemon_ids, opponent_active_nulls, rng)
        _, opponent_remaining = _sample(opponent_remaining, opponent_bench_nulls, rng)
        hidden_hand_count = max(0, _zone_count(theirs, "hand") - len(known_opponent_hand))
        sampled_hand, opponent_remaining = _sample(opponent_remaining, hidden_hand_count, rng)
        sampled_prize, opponent_remaining = _sample(opponent_remaining, opponent_prize_unknown, rng)
        if len(opponent_remaining) != _zone_count(theirs, "deck"):
            raise ValueError(f"opponent hidden-zone mismatch deck={len(opponent_remaining)} expected={_zone_count(theirs, 'deck')} opaque_active={opponent_active_nulls} opaque_other={opponent_bench_nulls}")
        revealed_active = [_card_id(card) for card in _sequence(theirs.get("active")) if isinstance(card, Mapping) and _card_id(card) is not None]
        return {
            "yourDeck": own_remaining,
            "yourPrize": full_own_prize,
            "opponentDeck": opponent_remaining,
            "opponentPrize": opponent_prize_known + sampled_prize,
            "opponentHand": known_opponent_hand + sampled_hand,
            "opponentActive": sampled_active if opponent_active_nulls else [int(card) for card in revealed_active],
        }

    def evaluate(self, observation: Mapping[str, Any], configuration: Any, own_deck: Sequence[int], selection: Sequence[int]) -> dict[str, Any]:
        config = self._config(configuration)
        options = _sequence(_mapping(observation.get("select")).get("option"))
        disabled = {
            "enabled": False, "reason": "local trace configuration not supplied", "source": "none",
            "searchTree": {"id": "root", "label": "Root", "status": "unavailable", "children": []},
            "rejectedBranches": [], "counterfactuals": [], "selectedPrediction": None, "hiddenBelief": {},
        }
        if not config.get("enabled"):
            return disabled
        opponent_deck = config.get("opponentDeck")
        if not isinstance(opponent_deck, Sequence) or isinstance(opponent_deck, (str, bytes, bytearray)):
            return {**disabled, "reason": "opponent deck unavailable"}
        select = _mapping(observation.get("select"))
        minimum = _integer(select.get("minCount"), 0)
        maximum = minimum if select.get("maxCount", minimum) is None else _integer(select.get("maxCount", minimum), minimum)
        if minimum != 1 or maximum != 1 or not options:
            return {**disabled, "reason": "root Search trace supports single-select decisions only"}

        actor = _integer(_mapping(observation.get("current")).get("yourIndex"), _integer(config.get("playerIndex"), 0))
        base = state_summary(observation, actor)
        simulations = max(1, min(8, _integer(config.get("simulationsPerAction"), 2)))
        budget_ms = max(5.0, min(250.0, float(config.get("budgetMs", 45.0))))
        started = time.perf_counter()
        stats: dict[int, list[tuple[float, dict[str, Any], dict[str, Any] | None]]] = {index: [] for index in range(len(options))}
        errors: list[str] = []
        api: Any | None = None
        seed_base = int(_stable_hash({"state": base["stateHash"], "own": list(own_deck), "opponent": list(opponent_deck)}), 16)
        try:
            api = self._load_api()
            converter = getattr(api, "to_observation_class", None)
            for simulation in range(simulations):
                hidden = self._determinize(api, observation, actor, own_deck, [int(card) for card in opponent_deck], seed_base + simulation)
                for index in range(len(options)):
                    if (time.perf_counter() - started) * 1000 >= budget_ms:
                        break
                    root_id = child_id = None
                    try:
                        obs_arg: Any = dict(observation)
                        if callable(converter):
                            obs_arg = converter(obs_arg)
                        root = api.search_begin(obs_arg, hidden["yourDeck"], hidden["yourPrize"], hidden["opponentDeck"], hidden["opponentPrize"], hidden["opponentHand"], hidden["opponentActive"], False)
                        root_id, _, _ = _state_parts(root)
                        child = api.search_step(root_id, [index])
                        child_id, child_observation, _ = _state_parts(child)
                        after = state_summary(child_observation, actor)
                        stats[index].append((_reward(base, after, actor), after, _cycle(base, after)))
                    except Exception as exc:
                        errors.append(f"option={index} {type(exc).__name__}: {exc}")
                    finally:
                        for search_id in (child_id, root_id):
                            if isinstance(search_id, int) and search_id >= 0:
                                try: api.search_release(search_id)
                                except Exception: pass
                if (time.perf_counter() - started) * 1000 >= budget_ms:
                    break
        except Exception as exc:
            return {**disabled, "reason": f"{type(exc).__name__}: {exc}", "errors": [str(exc)]}
        finally:
            if api is not None:
                try: api.search_end()
                except Exception: pass

        selected_index = selection[0] if len(selection) == 1 and isinstance(selection[0], int) else -1
        nodes, rejected, counterfactuals = [], [], []
        selected_prediction: dict[str, Any] | None = None
        selected_mean: float | None = None
        for index, option in enumerate(options):
            samples = stats[index]
            values = [sample[0] for sample in samples]
            mean = sum(values) / len(values) if values else None
            node = {
                "id": f"root:{index}", "label": _option_label(index, option),
                "status": "selected" if index == selected_index else "expanded" if samples else "unavailable",
                "ev": None if mean is None else mean * 100, "visits": len(values), "mean": mean,
                "worst": min(values) if values else None, "best": max(values) if values else None,
                "selected": index == selected_index, "pruned": False, "children": [],
                "source": "cg.api.search_begin/search_step",
            }
            nodes.append(node)
            cycle = next((sample[2] for sample in samples if sample[2]), None)
            if cycle:
                node.update({"pruned": index != selected_index, "status": "selected_cycle_warning" if index == selected_index else "pruned"})
                rejected.append({
                    "action": node["label"], "optionIndex": index, "reason": "RESOURCE_LOSS_CYCLE",
                    "evidence": cycle,
                    "metrics": {"energy": cycle["energy_delta"], "tempo": cycle["attack_delta"], "prize": cycle["prize_delta"], "damage": cycle["damage_delta"]},
                    "killedBy": "OfficialSearchCycleGuard", "source": "cg.api.search_step",
                })
            if samples:
                counterfactuals.append({
                    "action": node["label"], "optionIndex": index, "expectedValue": mean,
                    "visits": len(values), "selected": index == selected_index,
                    "source": "cg.api.search_step + search_state_heuristic",
                })
            if index == selected_index and samples:
                selected_mean, selected_prediction = mean, dict(samples[0][1])
        if selected_mean is not None:
            for row in counterfactuals:
                row["deltaFromSelected"] = None if row["expectedValue"] is None else row["expectedValue"] - selected_mean
        if selected_prediction is not None:
            selected_prediction["decisionId"] = None
        completed = sum(len(samples) for samples in stats.values())
        return {
            "enabled": completed > 0,
            "reason": "" if completed else (errors[0] if errors else "Search API produced no child states"),
            "source": "cg.api Search API", "elapsedMs": (time.perf_counter() - started) * 1000,
            "simulations": completed,
            "searchTree": {"id": "root", "label": "Root", "status": "expanded" if completed else "unavailable", "visits": completed, "children": nodes, "source": "cg.api.search_begin/search_step"},
            "rejectedBranches": rejected, "counterfactuals": counterfactuals,
            "selectedPrediction": selected_prediction,
            "hiddenBelief": {
                "source": "determinized from both uploaded deck lists", "samples": simulations,
                "opponentDeckSize": len(opponent_deck),
                "truthBoundary": "hidden cards are sampled for Search only; not treated as observed truth",
            },
            "errors": errors[:10],
        }
