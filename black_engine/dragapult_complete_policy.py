from __future__ import annotations

from collections import Counter
from typing import Any

from black_lab import card_id, damage_points, energy_count, remaining_hp, zone_cards

from .dragapult_policy import (
    AREA_ACTIVE,
    AREA_BENCH,
    AREA_DECK,
    AZELF,
    CINDERACE,
    CINDERACE_TURBO_FLARE,
    CRISPIN,
    DAWN,
    DRAKLOAK,
    DRAGAPULT_EX,
    DREEPY,
    DUSCLOPS,
    DUSKNOIR,
    DUSKULL,
    FIRE_ENERGY,
    NIGHT_STRETCHER,
    POFFIN,
    PRIME_CATCHER,
    PSYCHIC_ENERGY,
    RARE_CANDY,
    SCORBUNNY,
    SWITCH,
    T_ABILITY,
    T_END,
    T_EVOLVE,
    T_PLAY,
    T_RETREAT,
    _has_color,
    _missing_dragapult_colors,
    _resolved_option_card,
    _target_pokemon,
    DragapultCinderacePolicy,
    in_play_from_current,
)

T_YES, T_NO = 1, 2
AREA_HAND, AREA_LOOKING = 2, 12
CTX_TO_BENCH, CTX_TO_HAND, CTX_TO_DECK_BOTTOM = 5, 7, 10
CTX_DAMAGE_COUNTER, CTX_DAMAGE_COUNTER_ANY = 13, 14
CTX_ATTACH_FROM, CTX_ATTACH_TO, CTX_EFFECT_TARGET = 21, 22, 25
CTX_EVOLVE, CTX_ACTIVATE = 37, 43


class DragapultCompletePolicy(DragapultCinderacePolicy):
    """Final engine-source-grounded policy for BLACK Phantom Turbo.

    The parent contains the latest instance-aware core from the hybrid branch.
    This layer closes the remaining source-state-machine gaps without replacing
    that work: Drakloak LOOKING resolution, Rare Candy line arbitration,
    diversity-aware Poffin, selective Turbo Flare, and fail-closed Cursed Blast.
    """

    def build_context(self, obs: dict) -> dict:
        ctx = super().build_context(obs)
        current = ctx.get("_current") if isinstance(ctx.get("_current"), dict) else {}
        players = current.get("players") if isinstance(current.get("players"), list) else []
        me = int(ctx.get("_my_idx", 0))
        player = players[me] if 0 <= me < len(players) and isinstance(players[me], dict) else {}
        mine = in_play_from_current(current, me)
        opponent = int(ctx.get("_opponent_idx", 1))
        theirs = in_play_from_current(current, opponent)
        looking = []
        for value in current.get("looking") if isinstance(current.get("looking"), list) else []:
            if not isinstance(value, dict):
                continue
            owner = value.get("playerIndex")
            if type(owner) is not int or owner == me:
                looking.append(value)
        counts = Counter(card_id(value) for value in mine)
        dragapult_lines = [value for value in mine if card_id(value) in {DREEPY, DRAKLOAK, DRAGAPULT_EX}]
        ctx.update({
            "_select": obs.get("select") if isinstance(obs.get("select"), dict) else {},
            "deck_count": int(player.get("deckCount", 0) or 0),
            "bench_slots": max(0, 5 - len(player.get("bench") if isinstance(player.get("bench"), list) else [])),
            "my_counts": counts,
            "dragapult_lines": tuple(dragapult_lines),
            "azelf_ready": any(
                card_id(value) == AZELF
                and energy_count(value) >= 2
                and _has_color(value, PSYCHIC_ENERGY)
                for value in mine
            ),
            "_looking": looking,
            "_mine": mine,
            "_theirs": theirs,
        })
        return ctx

    @staticmethod
    def _option_player(option: dict, default: int) -> int:
        value = option.get("playerIndex", default)
        return value if type(value) is int and value in (0, 1) else default

    def _resolved_card(self, option: dict, ctx: dict) -> int:
        resolved = _resolved_option_card(option, ctx)
        if resolved >= 0:
            return resolved
        if option.get("area") == AREA_LOOKING and type(option.get("index")) is int:
            index = option["index"]
            looking = ctx.get("_looking")
            if isinstance(looking, list) and 0 <= index < len(looking):
                return card_id(looking[index])
        return -1

    def _resolved_target(self, option: dict, ctx: dict) -> dict[str, Any]:
        default = int(ctx.get("_my_idx", 0))
        target = _target_pokemon(option, ctx.get("_current"), default)
        if target:
            return target
        player_index = self._option_player(option, default)
        area, index = option.get("area"), option.get("index")
        if type(area) is int and type(index) is int and area in {AREA_ACTIVE, AREA_BENCH}:
            values = zone_cards(ctx.get("_current"), player_index, area)
            if 0 <= index < len(values) and isinstance(values[index], dict):
                return values[index]
        return {}

    @staticmethod
    def _prize_value(pokemon: dict[str, Any]) -> int:
        maximum = pokemon.get("maxHp") or pokemon.get("maxHP") or 0
        return 3 if type(maximum) in (int, float) and maximum >= 330 else 2 if type(maximum) in (int, float) and maximum >= 210 else 1

    def _missing_color_pressure(self, ctx: dict) -> tuple[int, int]:
        fire = psychic = 0
        for pokemon in ctx.get("dragapult_lines", ()):
            fire += int(not _has_color(pokemon, FIRE_ENERGY))
            psychic += int(not _has_color(pokemon, PSYCHIC_ENERGY))
        return fire, psychic

    def _route_card_value(self, cid: int, ctx: dict) -> float:
        counts = ctx.get("my_counts", Counter())
        hand = Counter(ctx.get("hand_ids", ()))
        fire_need, psychic_need = self._missing_color_pressure(ctx)
        if cid == PRIME_CATCHER and ctx.get("dragapult_ready"):
            return 1840
        if cid == DRAGAPULT_EX:
            return 1760 if counts[DRAKLOAK] > counts[DRAGAPULT_EX] else 1320
        if cid == DRAKLOAK:
            return 1730 if counts[DREEPY] > counts[DRAKLOAK] else 1260
        if cid == RARE_CANDY:
            stage2 = hand[DRAGAPULT_EX] + hand[DUSKNOIR] + hand[CINDERACE]
            basic = counts[DREEPY] + counts[DUSKULL] + counts[SCORBUNNY]
            return 1690 if stage2 and basic else 1040
        if cid == DUSKNOIR:
            return 1580 if counts[DUSCLOPS] else 980
        if cid == DUSCLOPS:
            return 1510 if counts[DUSKULL] else 930
        if cid == DAWN:
            return 1570 if counts[DRAGAPULT_EX] == 0 or counts[DRAKLOAK] < 2 else 1030
        if cid == CRISPIN:
            return 1540 if not ctx.get("dragapult_ready") else 820
        if cid == POFFIN:
            return 1510 if ctx.get("bench_slots", 0) >= 2 and (counts[DREEPY] < 2 or counts[DUSKULL] < 1) else 580
        if cid == NIGHT_STRETCHER:
            valuable = {DRAKLOAK, DRAGAPULT_EX, DUSCLOPS, DUSKNOIR, AZELF, FIRE_ENERGY, PSYCHIC_ENERGY}
            return 1470 if valuable.intersection(ctx.get("discard_ids", ())) else 540
        if cid == FIRE_ENERGY:
            return 1310 + 100 * fire_need
        if cid == PSYCHIC_ENERGY:
            return 1320 + 100 * psychic_need
        if cid == DREEPY:
            return 1450 if counts[DREEPY] < 2 else 820
        if cid == DUSKULL:
            return 1380 if counts[DUSKULL] < 1 else 720
        if cid == AZELF:
            return 1410 if ctx.get("opp_total_damage", 0) >= 70 and not ctx.get("azelf_in_play") else 720
        if cid == SWITCH:
            return 1430 if ctx.get("active_id") == CINDERACE and ctx.get("dragapult_ready") else 500
        return 600

    def _bomb_route_value(self, blast: int, ctx: dict) -> float:
        targets = ctx.get("_theirs", ())
        ko_targets = [value for value in targets if 0 < remaining_hp(value) <= blast]
        if ko_targets:
            prize = max(self._prize_value(value) for value in ko_targets)
            return 1900 + 280 * prize
        active_hp = int(ctx.get("opp_remaining_hp", 0) or 0)
        if ctx.get("dragapult_ready") and blast < active_hp <= blast + 200:
            return 1760
        if ctx.get("azelf_ready") and active_hp > blast and 10 + int(ctx.get("opp_total_damage", 0)) + blast >= active_hp:
            return 1650
        return -1400

    def _bomb_target_value(self, pokemon: dict[str, Any], blast: int, ctx: dict) -> float:
        hp = remaining_hp(pokemon)
        if hp <= 0:
            return -10000
        prize = self._prize_value(pokemon)
        if hp <= blast:
            return 2400 + 350 * prize - 2 * max(0, blast - hp)
        if ctx.get("dragapult_ready") and hp <= blast + 200:
            return 1840 + 160 * prize
        active = ctx.get("_theirs", ())
        is_active = bool(active and pokemon is active[0])
        if is_active and ctx.get("azelf_ready") and 10 + int(ctx.get("opp_total_damage", 0)) + blast >= hp:
            return 1710
        return -1000 + 40 * damage_points(pokemon)

    def _rare_candy_value(self, stage2: int, target: dict[str, Any], ctx: dict) -> float:
        target_id = card_id(target)
        if stage2 == DRAGAPULT_EX and target_id == DREEPY:
            ready = _missing_dragapult_colors(target) == 0
            return 2050 if ready else 1780 if not ctx.get("dragapult_in_play") else 1520
        if stage2 == DUSKNOIR and target_id == DUSKULL:
            return self._bomb_route_value(130, ctx) - 80
        if stage2 == CINDERACE and target_id == SCORBUNNY:
            missing = sum(_missing_dragapult_colors(value) for value in ctx.get("dragapult_lines", ()))
            return 1500 if not ctx.get("cinderace_in_play") and missing >= 2 else 260
        return 250

    def _energy_hint(self, ctx: dict) -> int:
        select = ctx.get("_select") if isinstance(ctx.get("_select"), dict) else {}
        candidates: list[int] = []
        for value in select.get("deck") if isinstance(select.get("deck"), list) else []:
            cid = card_id(value)
            if cid in {FIRE_ENERGY, PSYCHIC_ENERGY}:
                candidates.append(cid)
        for value in ctx.get("_looking", ()):
            cid = card_id(value)
            if cid in {FIRE_ENERGY, PSYCHIC_ENERGY}:
                candidates.append(cid)
        unique = set(candidates)
        return next(iter(unique)) if len(unique) == 1 else -1

    def _target_energy_value(self, energy: int, target: dict[str, Any], ctx: dict) -> float:
        if energy in {FIRE_ENERGY, PSYCHIC_ENERGY}:
            return self._score_energy_target(energy, target, ctx)
        cid = card_id(target)
        if cid in {DREEPY, DRAKLOAK, DRAGAPULT_EX}:
            missing = _missing_dragapult_colors(target)
            return 1500 + 260 * missing if missing else 120
        if cid == CINDERACE and ctx.get("active_id") == CINDERACE and energy_count(target) == 0:
            return 1380
        return 280

    def score_option(self, option: dict, ctx: dict) -> float:
        effect = int(ctx.get("effect_id", -1) or -1)
        context = int(ctx.get("select_context", -1) or -1)
        kind = option.get("type")
        cid = self._resolved_card(option, ctx)
        target = self._resolved_target(option, ctx)

        if effect == DRAKLOAK and context == CTX_ACTIVATE:
            return 1780 if kind == T_YES and ctx.get("deck_count", 0) >= 2 else 1450 if kind == T_NO else 0
        if effect == DRAKLOAK and context == CTX_TO_HAND:
            return self._route_card_value(cid, ctx)
        if effect == DRAKLOAK and context == CTX_TO_DECK_BOTTOM:
            return 2200 - self._route_card_value(cid, ctx)

        if effect == DRAGAPULT_EX and context == CTX_DAMAGE_COUNTER_ANY and target:
            return super().score_option(option, ctx) + 90 * self._prize_value(target)
        if effect == DUSCLOPS and context == CTX_DAMAGE_COUNTER and target:
            return self._bomb_target_value(target, 50, ctx)
        if effect == DUSKNOIR and context == CTX_DAMAGE_COUNTER and target:
            return self._bomb_target_value(target, 130, ctx)

        if effect == RARE_CANDY and context == CTX_EVOLVE:
            return self._rare_candy_value(cid, target, ctx)

        if effect in {CRISPIN, CINDERACE} and context in {CTX_ATTACH_TO, CTX_EFFECT_TARGET} and target:
            return self._target_energy_value(self._energy_hint(ctx), target, ctx)

        if kind == T_ABILITY and cid == DUSCLOPS:
            return self._bomb_route_value(50, ctx)
        if kind == T_ABILITY and cid == DUSKNOIR:
            return self._bomb_route_value(130, ctx)

        return super().score_option(option, ctx)

    def choose_multi(self, options: list, context: dict, minimum: int, maximum: int) -> list[int]:
        effect = int(context.get("effect_id", -1) or -1)
        select_context = int(context.get("select_context", -1) or -1)
        scored = [
            (self.score_option(value, context) if isinstance(value, dict) else -1e9, index, value)
            for index, value in enumerate(options)
        ]

        if effect == POFFIN and select_context == CTX_TO_BENCH:
            chosen: list[int] = []
            for wanted in (DREEPY, DUSKULL, DREEPY, AZELF, SCORBUNNY):
                matches = [
                    row for row in scored
                    if row[1] not in chosen and self._resolved_card(row[2], context) == wanted
                ]
                if matches and len(chosen) < maximum:
                    chosen.append(max(matches, key=lambda row: (row[0], row[1]))[1])
            if len(chosen) < minimum:
                for _, index, _ in sorted(scored, reverse=True):
                    if index not in chosen:
                        chosen.append(index)
                    if len(chosen) >= minimum:
                        break
            return chosen[:maximum]

        if effect == CRISPIN and select_context in {CTX_TO_HAND, CTX_ATTACH_FROM}:
            chosen: list[int] = []
            seen: set[int] = set()
            for _, index, option in sorted(scored, reverse=True):
                cid = self._resolved_card(option, context)
                if cid not in {FIRE_ENERGY, PSYCHIC_ENERGY} or cid in seen:
                    continue
                chosen.append(index)
                seen.add(cid)
                if len(chosen) >= maximum:
                    break
            return chosen if len(chosen) >= minimum else [index for _, index, _ in sorted(scored, reverse=True)[:minimum]]

        if effect == CINDERACE and select_context == CTX_ATTACH_FROM:
            fire_need, psychic_need = self._missing_color_pressure(context)
            wanted = [PSYCHIC_ENERGY] * min(2, psychic_need) + [FIRE_ENERGY] * min(2, fire_need)
            chosen: list[int] = []
            for energy in wanted:
                matches = [
                    row for row in scored
                    if row[1] not in chosen and self._resolved_card(row[2], context) == energy
                ]
                if matches and len(chosen) < maximum:
                    chosen.append(max(matches, key=lambda row: row[1])[1])
            if len(chosen) < minimum:
                for _, index, _ in sorted(scored, reverse=True):
                    if index not in chosen:
                        chosen.append(index)
                    if len(chosen) >= minimum:
                        break
            return chosen[:maximum]

        positive = [row for row in sorted(scored, reverse=True) if row[0] > 0]
        count = max(minimum, min(maximum, len(positive)))
        source = positive if len(positive) >= minimum else sorted(scored, reverse=True)
        return [index for _, index, _ in source[:count]]
