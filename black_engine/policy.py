from __future__ import annotations

from collections import Counter
from typing import Any

from .prize_truth import prize_value
from .support import (
    ScoredPolicy, active, bench, card_id, damage_points, energy_count, in_play,
    my_index, option_attack_id, option_card_id, remaining_hp, zone_cards,
)

T_YES, T_NO = 1, 2
T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14
AREA_DECK, AREA_ACTIVE, AREA_BENCH, AREA_LOOKING = 1, 4, 5, 12
CTX_TO_BENCH, CTX_TO_HAND, CTX_TO_DECK_BOTTOM = 5, 7, 10
CTX_DAMAGE_COUNTER, CTX_DAMAGE_COUNTER_ANY = 13, 14
CTX_ATTACH_FROM, CTX_ATTACH_TO, CTX_EFFECT_TARGET = 21, 22, 25
CTX_EVOLVE, CTX_ACTIVATE = 37, 43

SCORBUNNY, CINDERACE = 151, 666
DREEPY, DRAKLOAK, DRAGAPULT_EX = 119, 120, 121
DUSKULL, DUSCLOPS, DUSKNOIR = 131, 132, 133
AZELF = 217
FIRE_ENERGY, PSYCHIC_ENERGY = 2, 5
RARE_CANDY, POFFIN, PRIME_CATCHER = 1079, 1086, 1088
NIGHT_STRETCHER, SWITCH, TERA_ORB, POKE_PAD = 1097, 1123, 1127, 1152
BOSS, CRISPIN, LILLIE, DAWN = 1182, 1198, 1227, 1231
JET_HEADBUTT, PHANTOM_DIVE = 153, 154
SHADOW_BIND, NEUROKINESIS, TURBO_FLARE = 172, 292, 965


def _energy_ids(pokemon: dict[str, Any]) -> tuple[int, ...]:
    values = pokemon.get("energyCards")
    return tuple(card_id(value) for value in values if card_id(value) >= 0) if isinstance(values, list) else ()


def _has_color(pokemon: dict[str, Any], energy_id: int) -> bool:
    return energy_id in _energy_ids(pokemon)


def _missing_colors(pokemon: dict[str, Any]) -> int:
    return int(not _has_color(pokemon, FIRE_ENERGY)) + int(not _has_color(pokemon, PSYCHIC_ENERGY))


def _zone_from_current(current: dict | None, player_index: int, area: int) -> list:
    if area == AREA_LOOKING and isinstance(current, dict):
        return [value for value in current.get("looking") or [] if isinstance(value, dict) and value.get("playerIndex", player_index) == player_index]
    return zone_cards(current, player_index, area)


def _target_pokemon(option: dict, current: dict | None, default_player: int) -> dict[str, Any]:
    player_index = option.get("playerIndex", default_player)
    if type(player_index) is not int:
        player_index = default_player
    for area_key, index_key in (("inPlayArea", "inPlayIndex"), ("area", "index")):
        area, index = option.get(area_key), option.get(index_key)
        if type(area) is int and type(index) is int and area in {AREA_ACTIVE, AREA_BENCH}:
            values = _zone_from_current(current, player_index, area)
            if 0 <= index < len(values) and isinstance(values[index], dict):
                return values[index]
    return {}


def _resolved_card(option: dict, ctx: dict) -> int:
    resolved = option_card_id(option, ctx["current"], ctx["me"])
    if resolved >= 0:
        return resolved
    area, index = option.get("area"), option.get("index")
    if type(area) is int and type(index) is int:
        values = ctx["select"].get("deck") if area == AREA_DECK and isinstance(ctx["select"].get("deck"), list) else _zone_from_current(ctx["current"], option.get("playerIndex", ctx["me"]), area)
        if 0 <= index < len(values):
            return card_id(values[index])
    if option.get("type") in {T_ABILITY, T_RETREAT, T_ATTACK}:
        return card_id(_target_pokemon(option, ctx["current"], ctx["me"]))
    return -1


def _effect_id(select: dict) -> int:
    return card_id(select.get("effect"))


def _prize_value(pokemon: dict[str, Any]) -> int:
    return prize_value(pokemon)


class DragapultPolicy(ScoredPolicy):
    """Fast standalone policy for Dragapult/Drakloak/Cinderace/Dusknoir/Azelf."""

    def build_context(self, obs: dict) -> dict:
        me = my_index(obs)
        opp = 1 - me
        current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
        players = current.get("players") if isinstance(current.get("players"), list) else []
        mine, theirs = in_play(obs, me), in_play(obs, opp)
        my_player = players[me] if 0 <= me < len(players) and isinstance(players[me], dict) else {}
        select = obs.get("select") if isinstance(obs.get("select"), dict) else {}
        counts = Counter(card_id(value) for value in mine)
        lines = [value for value in mine if card_id(value) in {DREEPY, DRAKLOAK, DRAGAPULT_EX}]
        ready = [value for value in mine if card_id(value) == DRAGAPULT_EX and _missing_colors(value) == 0]
        return {
            "me": me, "opp": opp, "current": current, "select": select,
            "effect": _effect_id(select), "context": int(select.get("context", -1) or -1),
            "active_id": card_id(active(obs, me)), "opp_hp": remaining_hp(active(obs, opp)),
            "opp_damage": sum(damage_points(value) for value in theirs), "opp_bench": len(bench(obs, opp)),
            "bench_slots": max(0, 5 - len(bench(obs, me))), "deck_count": int(my_player.get("deckCount", 0) or 0),
            "hand_ids": tuple(card_id(value) for value in (my_player.get("hand") or []) if isinstance(value, dict)),
            "discard_ids": tuple(card_id(value) for value in (my_player.get("discard") or []) if isinstance(value, dict)),
            "counts": counts, "mine": mine, "theirs": theirs, "dragapult_lines": lines,
            "dragapult_ready": bool(ready), "ready_count": len(ready),
            "azelf_ready": any(card_id(value) == AZELF and _has_color(value, PSYCHIC_ENERGY) and energy_count(value) >= 2 for value in mine),
        }

    def _route_card_value(self, cid: int, ctx: dict) -> float:
        counts, hand = ctx["counts"], Counter(ctx["hand_ids"])
        fire_need = sum(not _has_color(value, FIRE_ENERGY) for value in ctx["dragapult_lines"])
        psychic_need = sum(not _has_color(value, PSYCHIC_ENERGY) for value in ctx["dragapult_lines"])
        if cid == PRIME_CATCHER and ctx["dragapult_ready"]: return 1900
        if cid == DRAGAPULT_EX: return 1800 if counts[DRAKLOAK] > counts[DRAGAPULT_EX] else 1300
        if cid == DRAKLOAK: return 1760 if counts[DREEPY] > counts[DRAKLOAK] else 1250
        if cid == RARE_CANDY: return 1700 if (hand[DRAGAPULT_EX] + hand[DUSKNOIR] + hand[CINDERACE]) and (counts[DREEPY] + counts[DUSKULL] + counts[SCORBUNNY]) else 980
        if cid == DUSKNOIR: return 1590 if counts[DUSCLOPS] else 950
        if cid == DUSCLOPS: return 1520 if counts[DUSKULL] else 900
        if cid == DAWN: return 1560 if counts[DRAGAPULT_EX] == 0 or counts[DRAKLOAK] < 2 else 1000
        if cid == CRISPIN: return 1540 if not ctx["dragapult_ready"] else 800
        if cid == POFFIN: return 1500 if ctx["bench_slots"] >= 2 and (counts[DREEPY] < 2 or counts[DUSKULL] < 1) else 550
        if cid == NIGHT_STRETCHER:
            valuable = {DRAKLOAK, DRAGAPULT_EX, DUSCLOPS, DUSKNOIR, AZELF, FIRE_ENERGY, PSYCHIC_ENERGY}
            return 1450 if valuable.intersection(ctx["discard_ids"]) else 500
        if cid == FIRE_ENERGY: return 1300 + 100 * fire_need
        if cid == PSYCHIC_ENERGY: return 1310 + 100 * psychic_need
        if cid == DREEPY: return 1430 if counts[DREEPY] < 2 else 800
        if cid == DUSKULL: return 1370 if counts[DUSKULL] < 1 else 700
        if cid == AZELF: return 1400 if ctx["opp_damage"] >= 70 and counts[AZELF] == 0 else 700
        if cid == SWITCH: return 1420 if ctx["active_id"] == CINDERACE and ctx["dragapult_ready"] else 450
        return 600

    def _energy_target_value(self, energy: int, target: dict, ctx: dict) -> float:
        cid = card_id(target)
        if cid in {DREEPY, DRAKLOAK, DRAGAPULT_EX}:
            if energy == FIRE_ENERGY and not _has_color(target, FIRE_ENERGY): return 1900
            if energy == PSYCHIC_ENERGY and not _has_color(target, PSYCHIC_ENERGY): return 1920
            return 180 if _missing_colors(target) == 0 else 700
        if cid == CINDERACE and ctx["active_id"] == CINDERACE and energy_count(target) == 0: return 1500
        if cid == AZELF and energy == PSYCHIC_ENERGY and ctx["opp_damage"] >= 80: return 1250
        if cid in {DUSKULL, DUSCLOPS, DUSKNOIR}: return 80
        return 300

    def _bomb_route(self, blast: int, ctx: dict) -> float:
        if any(0 < remaining_hp(value) <= blast for value in ctx["theirs"]): return 2200
        if ctx["dragapult_ready"] and blast < ctx["opp_hp"] <= blast + 200: return 1800
        if ctx["azelf_ready"] and ctx["opp_hp"] > blast and 10 + ctx["opp_damage"] + blast >= ctx["opp_hp"]: return 1650
        return -1400

    def _bomb_target(self, pokemon: dict, blast: int, ctx: dict) -> float:
        hp = remaining_hp(pokemon)
        if hp <= 0: return -10000
        if hp <= blast: return 2500 + 350 * _prize_value(pokemon) - max(0, blast - hp)
        if ctx["dragapult_ready"] and hp <= blast + 200: return 1800 + 150 * _prize_value(pokemon)
        return -900 + 30 * damage_points(pokemon)

    def _spread_target(self, pokemon: dict) -> float:
        hp = remaining_hp(pokemon)
        if hp <= 0: return -10000
        if hp <= 10: return 2500 + 300 * _prize_value(pokemon)
        after = hp - 10
        threshold = max(0, 420 - abs(after - 130) * 3, 300 - abs(after - 50) * 3)
        return 900 + threshold + 80 * _prize_value(pokemon) + min(250, damage_points(pokemon))

    def _rare_candy(self, stage2: int, target: dict, ctx: dict) -> float:
        base = card_id(target)
        if stage2 == DRAGAPULT_EX and base == DREEPY: return 2100 if _missing_colors(target) == 0 else 1750
        if stage2 == DUSKNOIR and base == DUSKULL: return self._bomb_route(130, ctx) - 80
        if stage2 == CINDERACE and base == SCORBUNNY: return 1450 if sum(_missing_colors(value) for value in ctx["dragapult_lines"]) >= 2 else 250
        return 200

    def score_option(self, option: dict, ctx: dict) -> float:
        kind, cid = option.get("type"), _resolved_card(option, ctx)
        target = _target_pokemon(option, ctx["current"], ctx["me"])
        effect, context, attack_id = ctx["effect"], ctx["context"], option_attack_id(option)
        if effect == DRAKLOAK and context == CTX_ACTIVATE: return 1800 if kind == T_YES and ctx["deck_count"] >= 2 else 1400 if kind == T_NO else 0
        if effect == DRAKLOAK and context == CTX_TO_HAND: return self._route_card_value(cid, ctx)
        if effect == DRAKLOAK and context == CTX_TO_DECK_BOTTOM: return 2200 - self._route_card_value(cid, ctx)
        if effect == DRAGAPULT_EX and context == CTX_DAMAGE_COUNTER_ANY and target: return self._spread_target(target)
        if effect == DUSCLOPS and context == CTX_DAMAGE_COUNTER and target: return self._bomb_target(target, 50, ctx)
        if effect == DUSKNOIR and context == CTX_DAMAGE_COUNTER and target: return self._bomb_target(target, 130, ctx)
        if effect == RARE_CANDY and context == CTX_EVOLVE: return self._rare_candy(cid, target, ctx)
        if effect in {DAWN, TERA_ORB, POKE_PAD, NIGHT_STRETCHER} and context == CTX_TO_HAND: return self._route_card_value(cid, ctx)
        if effect == POFFIN and context == CTX_TO_BENCH: return self._route_card_value(cid, ctx)
        if effect == CRISPIN and context == CTX_TO_HAND: return 1500 if cid in {FIRE_ENERGY, PSYCHIC_ENERGY} else 0
        if effect in {CRISPIN, CINDERACE} and context in {CTX_ATTACH_TO, CTX_EFFECT_TARGET} and target: return self._energy_target_value(cid if cid in {FIRE_ENERGY, PSYCHIC_ENERGY} else -1, target, ctx)
        if kind == T_ATTACK:
            if ctx["active_id"] == DRAGAPULT_EX:
                if attack_id == PHANTOM_DIVE: return 2150 if 0 < ctx["opp_hp"] <= 200 else 1700 + 50 * min(3, ctx["opp_bench"])
                if attack_id == JET_HEADBUTT: return 1450 if 0 < ctx["opp_hp"] <= 70 else 550
            if ctx["active_id"] == CINDERACE and attack_id == TURBO_FLARE: return 1900 if sum(_missing_colors(value) for value in ctx["dragapult_lines"]) >= 2 else 600
            if ctx["active_id"] == AZELF and attack_id == NEUROKINESIS:
                damage = 10 + ctx["opp_damage"]
                return 2200 if ctx["opp_hp"] and damage >= ctx["opp_hp"] else 1000 + min(700, damage)
            if ctx["active_id"] == DUSKNOIR and attack_id == SHADOW_BIND: return 1500 if 0 < ctx["opp_hp"] <= 150 else 600
            return 100
        if kind == T_ABILITY:
            if cid == DRAKLOAK: return 1800 if ctx["deck_count"] >= 2 else 100
            if cid == DUSCLOPS: return self._bomb_route(50, ctx)
            if cid == DUSKNOIR: return self._bomb_route(130, ctx)
            return 300
        if kind == T_EVOLVE:
            if cid == DRAKLOAK: return 1800 if ctx["counts"][DRAKLOAK] < 2 else 1450
            if cid == DRAGAPULT_EX: return 1900 if ctx["counts"][DRAGAPULT_EX] == 0 else 1500
            if cid == DUSCLOPS: return 1450
            if cid == DUSKNOIR: return 1500 + max(0, self._bomb_route(130, ctx) - 1400)
            if cid == CINDERACE: return 700
            return 250
        if kind == T_ENERGY: return self._energy_target_value(cid, target, ctx) if target else 250
        if kind == T_PLAY:
            if cid == POFFIN: return 1700 if ctx["bench_slots"] >= 2 and (ctx["counts"][DREEPY] < 2 or ctx["counts"][DUSKULL] < 1) else 500
            if cid == RARE_CANDY: return 1650 if any(value in ctx["hand_ids"] for value in (DRAGAPULT_EX, DUSKNOIR, CINDERACE)) else 400
            if cid == TERA_ORB: return 1500 if ctx["counts"][DRAGAPULT_EX] == 0 else 650
            if cid == POKE_PAD: return 1350 if ctx["counts"][DRAKLOAK] < 2 or ctx["counts"][DUSCLOPS] == 0 else 600
            if cid == DAWN: return 1650 if ctx["counts"][DRAGAPULT_EX] == 0 or ctx["counts"][DRAKLOAK] < 2 else 1000
            if cid == CRISPIN: return 1700 if not ctx["dragapult_ready"] else 700
            if cid == LILLIE: return 1400 if len(ctx["hand_ids"]) <= 4 else 750
            if cid == PRIME_CATCHER: return 2050 if ctx["dragapult_ready"] or ctx["azelf_ready"] else 750
            if cid == SWITCH: return 1950 if ctx["active_id"] == CINDERACE and ctx["dragapult_ready"] else 450
            if cid == BOSS: return 1850 if ctx["dragapult_ready"] else 450
            if cid == NIGHT_STRETCHER: return self._route_card_value(cid, ctx)
            return 250
        if kind == T_RETREAT: return 2000 if ctx["active_id"] == CINDERACE and ctx["dragapult_ready"] else 120
        if kind == T_END: return -400
        return 0

    def choose_multi(self, options: list, context: dict, minimum: int, maximum: int) -> list[int]:
        effect, select_context = context["effect"], context["context"]
        scored = [(self.score_option(option, context), index, option) for index, option in enumerate(options) if isinstance(option, dict)]
        if effect == POFFIN and select_context == CTX_TO_BENCH:
            chosen: list[int] = []
            for wanted in (DREEPY, DUSKULL, DREEPY, AZELF, SCORBUNNY):
                matches = [row for row in scored if row[1] not in chosen and _resolved_card(row[2], context) == wanted]
                if matches and len(chosen) < maximum: chosen.append(max(matches, key=lambda row: (row[0], row[1]))[1])
            for _, index, _ in sorted(scored, reverse=True):
                if len(chosen) >= minimum: break
                if index not in chosen: chosen.append(index)
            return chosen[:maximum]
        if effect == CRISPIN and select_context in {CTX_TO_HAND, CTX_ATTACH_FROM}:
            chosen, seen = [], set()
            for _, index, option in sorted(scored, reverse=True):
                cid = _resolved_card(option, context)
                if cid in {FIRE_ENERGY, PSYCHIC_ENERGY} and cid not in seen: chosen.append(index); seen.add(cid)
                if len(chosen) >= maximum: break
            return chosen if len(chosen) >= minimum else [index for _, index, _ in sorted(scored, reverse=True)[:minimum]]
        if effect == CINDERACE and select_context == CTX_ATTACH_FROM:
            fire_need = sum(not _has_color(value, FIRE_ENERGY) for value in context["dragapult_lines"])
            psychic_need = sum(not _has_color(value, PSYCHIC_ENERGY) for value in context["dragapult_lines"])
            wanted = [PSYCHIC_ENERGY] * min(2, psychic_need) + [FIRE_ENERGY] * min(2, fire_need)
            chosen: list[int] = []
            for energy in wanted:
                matches = [row for row in scored if row[1] not in chosen and _resolved_card(row[2], context) == energy]
                if matches and len(chosen) < maximum: chosen.append(matches[0][1])
            return chosen[:maximum]
        positive = [row for row in sorted(scored, reverse=True) if row[0] > 0]
        count = max(minimum, min(maximum, len(positive)))
        source = positive if len(positive) >= minimum else sorted(scored, reverse=True)
        return [index for _, index, _ in source[:count]]
