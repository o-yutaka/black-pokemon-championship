from __future__ import annotations

from typing import Any

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
    option_card_id,
    option_target_id,
    remaining_hp,
)

T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14

SCORBUNNY, CINDERACE = 151, 666
DREEPY, DRAKLOAK, DRAGAPULT_EX = 119, 120, 121
DUSKULL, DUSCLOPS, DUSKNOIR = 131, 132, 133
AZELF = 217

FIRE_ENERGY, PSYCHIC_ENERGY = 2, 5
RARE_CANDY, POFFIN, PRIME_CATCHER = 1079, 1086, 1088
NIGHT_STRETCHER, SWITCH, TERA_ORB, POKE_PAD = 1097, 1123, 1127, 1152
BOSS, CRISPIN, LILLIE, DAWN = 1182, 1198, 1227, 1231

DRAGAPULT_JET_HEADBUTT, DRAGAPULT_PHANTOM_DIVE = 153, 154
DUSKNOIR_SHADOW_BIND, AZELF_NEUROKINESIS, CINDERACE_TURBO_FLARE = 172, 292, 965


def _energy_card_ids(pokemon: dict[str, Any]) -> tuple[int, ...]:
    values = pokemon.get("energyCards")
    if not isinstance(values, list):
        return ()
    return tuple(card_id(value) for value in values if card_id(value) >= 0)


def _has_color(pokemon: dict[str, Any], energy_id: int) -> bool:
    return energy_id in _energy_card_ids(pokemon)


class DragapultCinderacePolicy(ScoredPolicy):
    """Deterministic fail-closed baseline for the BLACK championship shell.

    This is deliberately route-aware rather than a generic card-priority list:
    Cinderace opens and accelerates, Dragapult applies 200+spread pressure,
    Dusknoir converts the spread without consuming the attack, and Azelf turns
    accumulated damage counters into a one-Prize terminal attack.
    """

    def build_context(self, obs: dict) -> dict:
        me = my_index(obs)
        opponent = 1 - me
        mine = in_play(obs, me)
        theirs = in_play(obs, opponent)
        my_active = active(obs, me)
        opp_active = active(obs, opponent)
        hand = ((obs.get("current") or {}).get("players") or [{}, {}])[me].get("hand") or []
        discard = ((obs.get("current") or {}).get("players") or [{}, {}])[me].get("discard") or []
        ids = [card_id(value) for value in mine]
        opponent_damage = sum(damage_points(value) for value in theirs)
        dragapults = [value for value in mine if card_id(value) == DRAGAPULT_EX]
        return {
            "active_id": card_id(my_active),
            "active_energy": energy_count(my_active),
            "active_has_fire": _has_color(my_active, FIRE_ENERGY),
            "active_has_psychic": _has_color(my_active, PSYCHIC_ENERGY),
            "opp_remaining_hp": remaining_hp(opp_active),
            "opp_total_damage": opponent_damage,
            "opp_bench_count": len(bench(obs, opponent)),
            "my_bench_count": len(bench(obs, me)),
            "bench_energy": sum(energy_count(value) for value in bench(obs, me)),
            "dragapult_in_play": DRAGAPULT_EX in ids,
            "dragapult_ready": any(energy_count(value) >= 2 for value in dragapults),
            "drakloak_in_play": DRAKLOAK in ids,
            "duskull_in_play": DUSKULL in ids,
            "dusknoir_in_play": DUSKNOIR in ids,
            "azelf_in_play": AZELF in ids,
            "cinderace_in_play": CINDERACE in ids,
            "hand_ids": tuple(card_id(value) for value in hand),
            "discard_ids": tuple(card_id(value) for value in discard),
            "_current": obs.get("current"),
            "_my_idx": me,
        }

    def score_option(self, option: dict, ctx: dict) -> float:
        current = ctx.get("_current")
        my_idx = ctx.get("_my_idx", 0)
        kind = option.get("type")
        card = option_card_id(option, current, my_idx)
        target = option_target_id(option, current, my_idx)
        attack_id = option_attack_id(option)
        remaining = ctx["opp_remaining_hp"]

        if kind == T_ATTACK:
            if ctx["active_id"] == DRAGAPULT_EX:
                if attack_id == DRAGAPULT_PHANTOM_DIVE:
                    return 1500 if remaining and remaining <= 200 else 1240 + 35 * min(3, ctx["opp_bench_count"])
                if attack_id == DRAGAPULT_JET_HEADBUTT:
                    return 1420 if remaining and remaining <= 70 else 690
            if ctx["active_id"] == CINDERACE and attack_id == CINDERACE_TURBO_FLARE:
                route_open = ctx["my_bench_count"] > 0 and ctx["bench_energy"] < 3
                return 1390 if route_open else 640
            if ctx["active_id"] == AZELF and attack_id == AZELF_NEUROKINESIS:
                effective = 10 + ctx["opp_total_damage"]
                return 1540 if remaining and effective >= remaining else 900 + min(500, effective)
            if ctx["active_id"] == DUSKNOIR and attack_id == DUSKNOIR_SHADOW_BIND:
                return 1380 if remaining and remaining <= 150 else 760
            return 180

        if kind == T_EVOLVE:
            if card == DRAGAPULT_EX:
                return 1270
            if card == DRAKLOAK:
                return 1150
            if card == DUSKNOIR:
                return 1210
            if card == DUSCLOPS:
                return 1080
            if card == CINDERACE:
                return 930 if not ctx["cinderace_in_play"] else 410
            return 350

        if kind == T_ABILITY:
            if card == DUSKNOIR:
                terminal = any(0 < remaining_hp(value) <= 130 for value in in_play_from_current(current, 1 - my_idx))
                return 1510 if terminal else 1180
            if card == DUSCLOPS:
                terminal = any(0 < remaining_hp(value) <= 50 for value in in_play_from_current(current, 1 - my_idx))
                return 1440 if terminal else 980
            if card == DRAKLOAK or ctx["drakloak_in_play"]:
                return 1120
            return 520

        if kind == T_ENERGY:
            if target == CINDERACE and ctx["active_id"] == CINDERACE and ctx["active_energy"] == 0:
                return 1320
            if target in {DREEPY, DRAKLOAK, DRAGAPULT_EX}:
                if card == FIRE_ENERGY and not ctx["active_has_fire"]:
                    return 1190
                if card == PSYCHIC_ENERGY and not ctx["active_has_psychic"]:
                    return 1180
                return 1010
            if target == AZELF:
                return 900 if card == PSYCHIC_ENERGY else 260
            if target in {DUSKULL, DUSCLOPS, DUSKNOIR}:
                return 720 if card == PSYCHIC_ENERGY else 230
            return 420

        if kind == T_PLAY:
            if card == POFFIN:
                return 1210 if not (ctx["dragapult_in_play"] and ctx["duskull_in_play"]) else 720
            if card == RARE_CANDY:
                stage2_in_hand = any(value in ctx["hand_ids"] for value in (DRAGAPULT_EX, DUSKNOIR, CINDERACE))
                return 1260 if stage2_in_hand else 620
            if card == TERA_ORB:
                return 1180 if not ctx["dragapult_in_play"] else 650
            if card == POKE_PAD:
                return 1080 if not (ctx["drakloak_in_play"] and ctx["dusknoir_in_play"]) else 680
            if card == DAWN:
                return 1200 if not ctx["dragapult_in_play"] else 920
            if card == CRISPIN:
                return 1240 if not ctx["dragapult_ready"] else 760
            if card == LILLIE:
                return 1040
            if card == PRIME_CATCHER:
                return 1470 if ctx["dragapult_ready"] or ctx["azelf_in_play"] else 850
            if card == SWITCH:
                return 1430 if ctx["active_id"] == CINDERACE and ctx["dragapult_ready"] else 590
            if card == BOSS:
                return 1390 if ctx["dragapult_ready"] or ctx["azelf_in_play"] else 520
            if card == NIGHT_STRETCHER:
                valuable = any(value in ctx["discard_ids"] for value in (DUSKNOIR, DUSCLOPS, AZELF, DRAGAPULT_EX, FIRE_ENERGY, PSYCHIC_ENERGY))
                return 990 if valuable else 330
            if card in {DREEPY, DUSKULL, AZELF, SCORBUNNY}:
                return 920
            return 360

        if kind == T_RETREAT:
            if ctx["active_id"] == CINDERACE and ctx["dragapult_ready"]:
                return 1410
            if ctx["active_id"] not in {DRAGAPULT_EX, AZELF} and ctx["dragapult_in_play"]:
                return 1010
            return 160

        if kind == T_END:
            return -120
        return 0


def in_play_from_current(current: dict | None, index: int) -> list[dict]:
    if not isinstance(current, dict):
        return []
    players = current.get("players") or []
    if not (0 <= index < len(players)) or not isinstance(players[index], dict):
        return []
    player = players[index]
    active_values = player.get("active") if isinstance(player.get("active"), list) else []
    bench_values = player.get("bench") if isinstance(player.get("bench"), list) else []
    return [value for value in active_values + bench_values if isinstance(value, dict)]
