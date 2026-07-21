from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from black_lab import (
    ScoredPolicy,
    active,
    bench,
    card_id,
    damage_points,
    energy_count,
    in_play,
    my_index,
    option_attack_id,
    remaining_hp,
)

T_NUMBER, T_YES, T_NO, T_CARD = 0, 1, 2, 3
T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14

AREA_DECK, AREA_HAND, AREA_DISCARD, AREA_ACTIVE, AREA_BENCH, AREA_PRIZE = 1, 2, 3, 4, 5, 6
AREA_LOOKING = 12
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
BOSS, CRISPIN, HILDA, LILLIE, DAWN = 1182, 1198, 1225, 1227, 1231

DRAGAPULT_JET_HEADBUTT, DRAGAPULT_PHANTOM_DIVE = 153, 154
DUSKNOIR_SHADOW_BIND, AZELF_NEUROKINESIS, CINDERACE_TURBO_FLARE = 172, 292, 965

MEGA_EX_IDS = {
    652, 662, 678, 687, 695, 723, 737, 747, 754, 756,
    766, 772, 781, 790, 828, 849, 861, 868, 886, 896,
    904, 919, 928, 932, 939, 1006, 1031, 1040, 1056, 1064,
}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _select(obs: dict) -> dict:
    value = obs.get("select")
    return value if isinstance(value, dict) else {}


def _effect_id(select: dict) -> int:
    effect = select.get("effect")
    return card_id(effect)


def _player(current: dict | None, index: int) -> dict:
    if not isinstance(current, dict):
        return {}
    players = _list(current.get("players"))
    return players[index] if 0 <= index < len(players) and isinstance(players[index], dict) else {}


def _zone_values(current: dict | None, select: dict, player_index: int, area: int | None) -> list:
    if area == AREA_DECK:
        return _list(select.get("deck"))
    if area == AREA_LOOKING:
        if not isinstance(current, dict):
            return []
        values = []
        for value in _list(current.get("looking")):
            if not isinstance(value, dict):
                continue
            owner = value.get("playerIndex")
            if type(owner) is not int or owner == player_index:
                values.append(value)
        return values
    p = _player(current, player_index)
    key = {
        AREA_HAND: "hand",
        AREA_DISCARD: "discard",
        AREA_ACTIVE: "active",
        AREA_BENCH: "bench",
        AREA_PRIZE: "prize",
    }.get(area)
    return _list(p.get(key)) if key else []


def _resolve_card(option: dict, current: dict | None, select: dict, default_player: int) -> int:
    for key in ("card", "cardId", "id"):
        value = card_id(option.get(key))
        if value >= 0:
            return value
    player_index = option.get("playerIndex", default_player)
    player_index = player_index if type(player_index) is int and player_index in (0, 1) else default_player
    area = option.get("area")
    if area is None and option.get("type") == T_PLAY:
        area = AREA_HAND
    index = option.get("index")
    if type(area) is int and type(index) is int:
        values = _zone_values(current, select, player_index, area)
        if 0 <= index < len(values):
            return card_id(values[index])
    source_area, source_index = option.get("inPlayArea"), option.get("inPlayIndex")
    if type(source_area) is int and type(source_index) is int:
        values = _zone_values(current, select, player_index, source_area)
        if 0 <= source_index < len(values):
            return card_id(values[source_index])
    return -1


def _target_pokemon(option: dict, current: dict | None, select: dict, default_player: int) -> dict:
    player_index = option.get("targetPlayerIndex", option.get("playerIndex", default_player))
    player_index = player_index if type(player_index) is int and player_index in (0, 1) else default_player
    for area_key, index_key in (("inPlayArea", "inPlayIndex"), ("area", "index")):
        area, index = option.get(area_key), option.get(index_key)
        if type(area) is int and type(index) is int and area in (AREA_ACTIVE, AREA_BENCH):
            values = _zone_values(current, select, player_index, area)
            if 0 <= index < len(values) and isinstance(values[index], dict):
                return values[index]
    return {}


def _energy_ids(pokemon: dict) -> tuple[int, ...]:
    values = pokemon.get("energyCards")
    if not isinstance(values, list):
        return ()
    return tuple(value for value in (card_id(card) for card in values) if value >= 0)


def _has_color(pokemon: dict, energy_id: int) -> bool:
    return energy_id in _energy_ids(pokemon)


def _ready_dragapult(pokemon: dict) -> bool:
    return card_id(pokemon) == DRAGAPULT_EX and _has_color(pokemon, FIRE_ENERGY) and _has_color(pokemon, PSYCHIC_ENERGY)


def _prize_value(pokemon: dict) -> int:
    cid = card_id(pokemon)
    if cid in MEGA_EX_IDS:
        return 3
    maximum = pokemon.get("maxHp")
    if type(maximum) in (int, float) and int(maximum) >= 220:
        return 2
    return 1


def _count_ids(values: Iterable[dict]) -> Counter:
    return Counter(card_id(value) for value in values)


class DragapultCinderacePolicy(ScoredPolicy):
    """Engine-source-grounded championship policy for Dragapult/Cinderace.

    Every follow-up selection window is treated as part of the source card's
    state machine instead of as an isolated generic option list:

    * Drakloak Recon Directive: LOOKING -> TO_HAND -> bottom the other card.
    * Phantom Dive: six repeated DAMAGE_COUNTER_ANY selections.
    * Dusclops/Dusknoir Cursed Blast: self-KO + one target.
    * Rare Candy: one EVOLVE option carries Stage 2 and Basic target.
    * Crispin/Turbo Flare: choose Energy and the exact receiving instance.
    """

    def build_context(self, obs: dict) -> dict:
        me = my_index(obs)
        opponent = 1 - me
        current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
        select = _select(obs)
        mine = in_play(obs, me)
        theirs = in_play(obs, opponent)
        my_active = active(obs, me)
        opp_active = active(obs, opponent)
        hand = _list(_player(current, me).get("hand"))
        discard = _list(_player(current, me).get("discard"))
        my_counts = _count_ids(mine)
        opp_damage = sum(damage_points(value) for value in theirs)
        ready = [value for value in mine if _ready_dragapult(value)]
        dragapult_lines = [value for value in mine if card_id(value) in {DREEPY, DRAKLOAK, DRAGAPULT_EX}]
        return {
            "active_id": card_id(my_active),
            "opp_remaining_hp": remaining_hp(opp_active),
            "opp_total_damage": opp_damage,
            "opp_bench_count": len(bench(obs, opponent)),
            "bench_slots": max(0, 5 - len(bench(obs, me))),
            "my_prize": len(_list(_player(current, me).get("prize"))),
            "opp_prize": len(_list(_player(current, opponent).get("prize"))),
            "my_counts": my_counts,
            "ready_dragapults": tuple(ready),
            "dragapult_lines": tuple(dragapult_lines),
            "dragapult_ready": bool(ready),
            "drakloak_count": my_counts[DRAKLOAK],
            "dragapult_count": my_counts[DRAGAPULT_EX],
            "duskull_count": my_counts[DUSKULL],
            "dusclops_count": my_counts[DUSCLOPS],
            "dusknoir_count": my_counts[DUSKNOIR],
            "azelf_in_play": my_counts[AZELF] > 0,
            "cinderace_in_play": my_counts[CINDERACE] > 0,
            "hand_ids": tuple(card_id(value) for value in hand),
            "discard_ids": tuple(card_id(value) for value in discard),
            "deck_count": int(_player(current, me).get("deckCount", 0) or 0),
            "select_context": int(select.get("context", -1) or -1),
            "select_type": int(select.get("type", -1) or -1),
            "effect_id": _effect_id(select),
            "_current": current,
            "_select": select,
            "_my_idx": me,
            "_opp_idx": opponent,
            "_mine": mine,
            "_theirs": theirs,
        }

    def _resolved_card(self, option: dict, ctx: dict) -> int:
        return _resolve_card(option, ctx["_current"], ctx["_select"], ctx["_my_idx"])

    def _resolved_target(self, option: dict, ctx: dict) -> dict:
        return _target_pokemon(option, ctx["_current"], ctx["_select"], ctx["_my_idx"])

    def _missing_color_pressure(self, ctx: dict) -> tuple[int, int]:
        fire = psychic = 0
        for pokemon in ctx["dragapult_lines"]:
            if not _has_color(pokemon, FIRE_ENERGY):
                fire += 1
            if not _has_color(pokemon, PSYCHIC_ENERGY):
                psychic += 1
        return fire, psychic

    def _recon_value(self, cid: int, ctx: dict) -> float:
        if cid < 0:
            return 0
        counts = ctx["my_counts"]
        hand = Counter(ctx["hand_ids"])
        fire_need, psychic_need = self._missing_color_pressure(ctx)
        if cid == PRIME_CATCHER and ctx["dragapult_ready"]:
            return 1740
        if cid == DRAGAPULT_EX:
            return 1650 if counts[DRAKLOAK] > counts[DRAGAPULT_EX] else 1240
        if cid == DRAKLOAK:
            return 1600 if counts[DREEPY] > counts[DRAKLOAK] else 1180
        if cid == RARE_CANDY:
            stage2 = hand[DRAGAPULT_EX] + hand[DUSKNOIR] + hand[CINDERACE]
            basics = counts[DREEPY] + counts[DUSKULL] + counts[SCORBUNNY]
            return 1580 if stage2 and basics else 1080
        if cid == DUSKNOIR:
            return 1510 if counts[DUSCLOPS] else 1040
        if cid == DUSCLOPS:
            return 1460 if counts[DUSKULL] else 990
        if cid == DAWN:
            return 1450 if counts[DRAGAPULT_EX] == 0 or counts[DRAKLOAK] < 2 else 1040
        if cid == CRISPIN:
            return 1430 if not ctx["dragapult_ready"] else 880
        if cid == TERA_ORB:
            return 1400 if counts[DRAGAPULT_EX] == 0 else 820
        if cid == POFFIN:
            return 1390 if ctx["bench_slots"] >= 2 and (counts[DREEPY] < 2 or counts[DUSKULL] < 1) else 650
        if cid == NIGHT_STRETCHER:
            valuable = {DRAKLOAK, DRAGAPULT_EX, DUSCLOPS, DUSKNOIR, AZELF, FIRE_ENERGY, PSYCHIC_ENERGY}
            return 1360 if valuable.intersection(ctx["discard_ids"]) else 620
        if cid == FIRE_ENERGY:
            return 1340 + 90 * fire_need
        if cid == PSYCHIC_ENERGY:
            return 1350 + 90 * psychic_need
        if cid == DREEPY:
            return 1330 if counts[DREEPY] < 2 else 850
        if cid == DUSKULL:
            return 1260 if counts[DUSKULL] < 1 else 760
        if cid == AZELF:
            return 1300 if ctx["opp_total_damage"] >= 80 and not ctx["azelf_in_play"] else 760
        if cid == LILLIE:
            return 1250 if len(ctx["hand_ids"]) <= 3 else 780
        if cid == BOSS:
            return 1380 if ctx["dragapult_ready"] else 500
        if cid == SWITCH:
            return 1370 if ctx["active_id"] == CINDERACE and ctx["dragapult_ready"] else 500
        if cid == POKE_PAD:
            return 1180 if counts[DRAKLOAK] < 2 or counts[DUSCLOPS] == 0 else 720
        if cid == CINDERACE:
            return 680
        return 600

    def _spread_target_value(self, pokemon: dict, ctx: dict) -> float:
        if not pokemon:
            return 0
        rem = remaining_hp(pokemon)
        prize = _prize_value(pokemon)
        if 0 < rem <= 10:
            return 2200 + 300 * prize
        after = max(0, rem - 10)
        value = 900 + 40 * prize
        if rem > 130 >= after:
            value += 420
        if rem > 50 >= after:
            value += 300
        value += max(0, 360 - after)
        if card_id(pokemon) in MEGA_EX_IDS:
            value += 300
        return value

    def _blast_target_value(self, pokemon: dict, blast: int, ctx: dict) -> float:
        if not pokemon:
            return 0
        rem = remaining_hp(pokemon)
        prize = _prize_value(pokemon)
        if 0 < rem <= blast:
            return 2400 + 420 * prize - max(0, blast - rem)
        active = bool(ctx["_theirs"] and pokemon is ctx["_theirs"][0])
        value = 500 + 70 * prize
        if active and ctx["dragapult_ready"] and rem <= blast + 200:
            value += 1150
        if ctx["azelf_in_play"] and 10 + ctx["opp_total_damage"] + blast >= ctx["opp_remaining_hp"] > 0:
            value += 850
        if card_id(pokemon) in MEGA_EX_IDS:
            value += 260
        return value

    def _bomb_activation_value(self, blast: int, ctx: dict) -> float:
        targets = ctx["_theirs"]
        if any(0 < remaining_hp(p) <= blast for p in targets):
            best_prize = max((_prize_value(p) for p in targets if 0 < remaining_hp(p) <= blast), default=1)
            return 1800 + 300 * best_prize
        if ctx["dragapult_ready"] and 0 < ctx["opp_remaining_hp"] <= blast + 200:
            return 1680
        if ctx["azelf_in_play"] and 10 + ctx["opp_total_damage"] + blast >= ctx["opp_remaining_hp"] > 0:
            return 1510
        return -900

    def _candy_value(self, stage2: int, target: dict, ctx: dict) -> float:
        target_id = card_id(target)
        if stage2 == DRAGAPULT_EX and target_id == DREEPY:
            carries = _has_color(target, FIRE_ENERGY) and _has_color(target, PSYCHIC_ENERGY)
            return 1880 if carries or ctx["dragapult_count"] == 0 else 1500
        if stage2 == DUSKNOIR and target_id == DUSKULL:
            return self._bomb_activation_value(130, ctx) - 80
        if stage2 == CINDERACE and target_id == SCORBUNNY:
            missing = sum(
                2 - min(2, energy_count(p))
                for p in bench_from_current(ctx["_current"], ctx["_my_idx"])
                if card_id(p) in {DREEPY, DRAKLOAK, DRAGAPULT_EX}
            )
            return 1420 if not ctx["cinderace_in_play"] and missing >= 2 else 420
        return 300

    def _basic_search_value(self, cid: int, ctx: dict) -> float:
        counts = ctx["my_counts"]
        if cid == DREEPY:
            return 1700 if counts[DREEPY] < 2 else 1150
        if cid == DUSKULL:
            return 1550 if counts[DUSKULL] < 1 else 960
        if cid == AZELF:
            return 1450 if ctx["opp_total_damage"] >= 60 and not ctx["azelf_in_play"] else 900
        if cid == SCORBUNNY:
            return 520 if not ctx["cinderace_in_play"] else 180
        return 300

    def _dawn_value(self, cid: int, ctx: dict) -> float:
        if cid in {DREEPY, DUSKULL, AZELF, SCORBUNNY}:
            return self._basic_search_value(cid, ctx)
        if cid == DRAKLOAK:
            return 1800 if ctx["drakloak_count"] < 2 else 1300
        if cid == DUSCLOPS:
            return 1580 if ctx["duskull_count"] > ctx["dusclops_count"] else 980
        if cid == DRAGAPULT_EX:
            return 1840 if ctx["dragapult_count"] == 0 or ctx["drakloak_count"] > ctx["dragapult_count"] else 1320
        if cid == DUSKNOIR:
            return 1600 if ctx["dusclops_count"] else 1020
        if cid == CINDERACE:
            return 500
        return 300

    def _energy_target_value(self, energy_id: int, target: dict, ctx: dict) -> float:
        cid = card_id(target)
        if cid in {DREEPY, DRAKLOAK, DRAGAPULT_EX}:
            has_fire = _has_color(target, FIRE_ENERGY)
            has_psychic = _has_color(target, PSYCHIC_ENERGY)
            if energy_id == FIRE_ENERGY and not has_fire:
                return 1900 if not ctx["dragapult_ready"] else 1450
            if energy_id == PSYCHIC_ENERGY and not has_psychic:
                return 1920 if not ctx["dragapult_ready"] else 1470
            return 250 if has_fire and has_psychic else 760
        if cid == CINDERACE and ctx["active_id"] == CINDERACE and energy_count(target) == 0:
            return 1760 if ctx["dragapult_lines"] else 620
        if cid == AZELF:
            if energy_id == PSYCHIC_ENERGY and ctx["opp_total_damage"] >= 80:
                return 1320
            return 480
        if cid in {DUSKULL, DUSCLOPS, DUSKNOIR}:
            return 100
        return 350

    def score_option(self, option: dict, ctx: dict) -> float:
        current, select = ctx["_current"], ctx["_select"]
        kind = option.get("type")
        cid = self._resolved_card(option, ctx)
        target = self._resolved_target(option, ctx)
        attack_id = option_attack_id(option)
        context = ctx["select_context"]
        effect = ctx["effect_id"]

        if context == CTX_ACTIVATE and effect in {DRAKLOAK, DUSCLOPS, DUSKNOIR}:
            activate = kind == T_YES
            if effect == DRAKLOAK:
                return 1750 if activate and ctx["deck_count"] >= 2 else 200 if activate else 0
            blast = 50 if effect == DUSCLOPS else 130
            route = self._bomb_activation_value(blast, ctx)
            return route if activate else (1450 if route < 500 else 0)

        if effect == DRAKLOAK and context == CTX_TO_HAND:
            return self._recon_value(cid, ctx)
        if effect == DRAKLOAK and context == CTX_TO_DECK_BOTTOM:
            return 2000 - self._recon_value(cid, ctx)

        if effect == DRAGAPULT_EX and context == CTX_DAMAGE_COUNTER_ANY:
            pokemon = target or self._resolved_card_pokemon(option, ctx, ctx["_opp_idx"])
            return self._spread_target_value(pokemon, ctx)

        if effect in {DUSCLOPS, DUSKNOIR} and context == CTX_DAMAGE_COUNTER:
            blast = 50 if effect == DUSCLOPS else 130
            pokemon = target or self._resolved_card_pokemon(option, ctx, ctx["_opp_idx"])
            return self._blast_target_value(pokemon, blast, ctx)

        if effect == RARE_CANDY and context == CTX_EVOLVE:
            return self._candy_value(cid, target, ctx)

        if effect == DAWN and context == CTX_TO_HAND:
            return self._dawn_value(cid, ctx)
        if effect == POFFIN and context == CTX_TO_BENCH:
            return self._basic_search_value(cid, ctx)
        if effect == POKE_PAD and context == CTX_TO_HAND:
            return self._recon_value(cid, ctx)
        if effect == TERA_ORB and context == CTX_TO_HAND:
            return 1800 if cid == DRAGAPULT_EX else 0
        if effect == NIGHT_STRETCHER and context == CTX_TO_HAND:
            return self._recon_value(cid, ctx) + (300 if cid in ctx["discard_ids"] else 0)

        if effect == CRISPIN and context == CTX_TO_HAND:
            fire_need, psychic_need = self._missing_color_pressure(ctx)
            urgent = FIRE_ENERGY if fire_need > psychic_need else PSYCHIC_ENERGY
            return 1540 if cid in {FIRE_ENERGY, PSYCHIC_ENERGY} and cid != urgent else 1280
        if effect in {CRISPIN, CINDERACE} and context in {CTX_ATTACH_FROM, CTX_ATTACH_TO, CTX_EFFECT_TARGET}:
            energy_id = cid if cid in {FIRE_ENERGY, PSYCHIC_ENERGY} else self._effect_energy_hint(select)
            if target:
                return self._energy_target_value(energy_id, target, ctx)
            target_as_card = self._resolved_card_pokemon(option, ctx, ctx["_my_idx"])
            if target_as_card:
                return self._energy_target_value(energy_id, target_as_card, ctx)
            return 1400 if cid in {FIRE_ENERGY, PSYCHIC_ENERGY} else 400

        if kind == T_ATTACK:
            remaining = ctx["opp_remaining_hp"]
            if ctx["active_id"] == DRAGAPULT_EX:
                if attack_id == DRAGAPULT_PHANTOM_DIVE:
                    return 2100 if 0 < remaining <= 200 else 1730 + 70 * min(3, ctx["opp_bench_count"])
                if attack_id == DRAGAPULT_JET_HEADBUTT:
                    return 1450 if 0 < remaining <= 70 else 620
            if ctx["active_id"] == CINDERACE and attack_id == CINDERACE_TURBO_FLARE:
                missing = sum(
                    (not _has_color(p, FIRE_ENERGY)) + (not _has_color(p, PSYCHIC_ENERGY))
                    for p in ctx["dragapult_lines"]
                )
                return 1840 if missing >= 2 else 730
            if ctx["active_id"] == AZELF and attack_id == AZELF_NEUROKINESIS:
                effective = 10 + ctx["opp_total_damage"]
                return 2200 if remaining and effective >= remaining else 1040 + min(700, effective)
            if ctx["active_id"] == DUSKNOIR and attack_id == DUSKNOIR_SHADOW_BIND:
                return 1500 if remaining and remaining <= 150 else 650
            return 200

        if kind == T_ABILITY:
            if cid == DRAKLOAK:
                return 1760 if ctx["deck_count"] >= 2 else 100
            if cid == DUSCLOPS:
                return self._bomb_activation_value(50, ctx)
            if cid == DUSKNOIR:
                return self._bomb_activation_value(130, ctx)
            return 400

        if kind == T_EVOLVE:
            if cid == DRAKLOAK:
                return 1810 if ctx["drakloak_count"] < 2 else 1450
            if cid == DRAGAPULT_EX:
                return 1880 if ctx["dragapult_count"] == 0 else 1540
            if cid == DUSCLOPS:
                return 1470
            if cid == DUSKNOIR:
                return 1520 + max(0, self._bomb_activation_value(130, ctx) - 1200)
            if cid == CINDERACE:
                return 760 if not ctx["cinderace_in_play"] else 260
            return 350

        if kind == T_ENERGY:
            return self._energy_target_value(cid, target, ctx)

        if kind == T_PLAY:
            if cid == POFFIN:
                return 1660 if ctx["bench_slots"] >= 2 and (ctx["my_counts"][DREEPY] < 2 or ctx["my_counts"][DUSKULL] < 1) else 650
            if cid == RARE_CANDY:
                stage2 = any(value in ctx["hand_ids"] for value in (DRAGAPULT_EX, DUSKNOIR, CINDERACE))
                basic = ctx["my_counts"][DREEPY] + ctx["my_counts"][DUSKULL] + ctx["my_counts"][SCORBUNNY]
                return 1700 if stage2 and basic else 480
            if cid == TERA_ORB:
                return 1510 if ctx["dragapult_count"] == 0 else 690
            if cid == POKE_PAD:
                return 1370 if ctx["drakloak_count"] < 2 or ctx["dusclops_count"] == 0 else 700
            if cid == DAWN:
                return 1650 if ctx["dragapult_count"] == 0 or ctx["drakloak_count"] < 2 else 1080
            if cid == CRISPIN:
                return 1690 if not ctx["dragapult_ready"] else 780
            if cid == LILLIE:
                dead_cinderace = Counter(ctx["hand_ids"])[CINDERACE]
                return 1420 if len(ctx["hand_ids"]) <= 4 or dead_cinderace >= 2 else 870
            if cid == PRIME_CATCHER:
                return 2010 if ctx["dragapult_ready"] or ctx["azelf_in_play"] else 820
            if cid == SWITCH:
                return 1940 if ctx["active_id"] == CINDERACE and ctx["dragapult_ready"] else 540
            if cid == BOSS:
                lethal_bench = any(0 < remaining_hp(p) <= 200 for p in bench_from_current(current, ctx["_opp_idx"]))
                return 1900 if ctx["dragapult_ready"] and lethal_bench else 520
            if cid == NIGHT_STRETCHER:
                valuable = {DRAKLOAK, DRAGAPULT_EX, DUSCLOPS, DUSKNOIR, AZELF, FIRE_ENERGY, PSYCHIC_ENERGY}
                return 1440 if valuable.intersection(ctx["discard_ids"]) else 370
            if cid in {DREEPY, DUSKULL, AZELF, SCORBUNNY}:
                return self._basic_search_value(cid, ctx)
            return 330

        if kind == T_RETREAT:
            if ctx["active_id"] == CINDERACE and ctx["dragapult_ready"]:
                return 1980
            if ctx["active_id"] not in {DRAGAPULT_EX, AZELF} and ctx["dragapult_ready"]:
                return 1540
            return 130

        if kind == T_END:
            return -400
        return 0

    def _resolved_card_pokemon(self, option: dict, ctx: dict, default_player: int) -> dict:
        current, select = ctx["_current"], ctx["_select"]
        player_index = option.get("playerIndex", default_player)
        player_index = player_index if type(player_index) is int and player_index in (0, 1) else default_player
        area, index = option.get("area"), option.get("index")
        if type(area) is int and type(index) is int and area in (AREA_ACTIVE, AREA_BENCH):
            values = _zone_values(current, select, player_index, area)
            if 0 <= index < len(values) and isinstance(values[index], dict):
                return values[index]
        return {}

    @staticmethod
    def _effect_energy_hint(select: dict) -> int:
        effect = select.get("effect")
        if isinstance(effect, dict):
            for key in ("energyId", "cardId", "selectedCardId"):
                value = effect.get(key)
                if value in {FIRE_ENERGY, PSYCHIC_ENERGY}:
                    return int(value)
        return PSYCHIC_ENERGY

    def choose_multi(self, options: list, context: dict, minimum: int, maximum: int) -> list[int]:
        effect = context["effect_id"]
        select_context = context["select_context"]
        scored = [
            (self.score_option(value, context) if isinstance(value, dict) else -1e9, index, value)
            for index, value in enumerate(options)
        ]

        if effect == POFFIN and select_context == CTX_TO_BENCH:
            chosen: list[int] = []
            desired = [DREEPY, DUSKULL, AZELF, DREEPY, SCORBUNNY]
            for wanted in desired:
                candidates = [
                    row for row in scored
                    if row[1] not in chosen and self._resolved_card(row[2], context) == wanted
                ]
                if candidates and len(chosen) < maximum:
                    chosen.append(max(candidates, key=lambda row: (row[0], row[1]))[1])
            if len(chosen) < minimum:
                for _, index, _ in sorted(scored, reverse=True):
                    if index not in chosen:
                        chosen.append(index)
                    if len(chosen) >= minimum:
                        break
            return chosen[:maximum]

        if effect == CINDERACE and select_context == CTX_ATTACH_TO:
            fire_need, psychic_need = self._missing_color_pressure(context)
            wanted = [PSYCHIC_ENERGY] * psychic_need + [FIRE_ENERGY] * fire_need
            chosen: list[int] = []
            for energy in wanted:
                candidates = [
                    row for row in scored
                    if row[1] not in chosen and self._resolved_card(row[2], context) == energy
                ]
                if candidates and len(chosen) < maximum:
                    chosen.append(max(candidates, key=lambda row: row[1])[1])
            if not chosen and minimum > 0:
                chosen = [index for _, index, _ in sorted(scored, reverse=True)[:minimum]]
            return chosen[:maximum]

        positive = sorted((row for row in scored if row[0] > 0), reverse=True)
        count = max(minimum, min(maximum, len(positive)))
        source = positive if len(positive) >= minimum else sorted(scored, reverse=True)
        return [index for _, index, _ in source[:count]]


def bench_from_current(current: dict | None, index: int) -> list[dict]:
    return [value for value in _list(_player(current, index).get("bench")) if isinstance(value, dict)]
