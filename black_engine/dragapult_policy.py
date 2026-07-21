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
    zone_cards,
)

T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14
AREA_DECK, AREA_ACTIVE, AREA_BENCH = 1, 4, 5

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


def _serial(pokemon: dict[str, Any]) -> int:
    value = pokemon.get("serial")
    return value if type(value) is int else -1


def _pokemon_from_location(current: dict | None, player_index: int, area: Any, index: Any) -> dict[str, Any]:
    if not isinstance(area, int) or not isinstance(index, int):
        return {}
    cards = zone_cards(current, player_index, area)
    if 0 <= index < len(cards) and isinstance(cards[index], dict):
        return cards[index]
    return {}


def _target_pokemon(option: dict, current: dict | None, default_player_index: int) -> dict[str, Any]:
    player_index = option.get("playerIndex", default_player_index)
    if type(player_index) is not int:
        player_index = default_player_index
    target = _pokemon_from_location(current, player_index, option.get("inPlayArea"), option.get("inPlayIndex"))
    if target:
        return target
    return _pokemon_from_location(current, player_index, option.get("area"), option.get("index"))


def _effect_id(select: dict[str, Any]) -> int:
    effect = select.get("effect")
    return card_id(effect)


def _resolved_option_card(option: dict, ctx: dict) -> int:
    current = ctx.get("_current")
    my_idx = ctx.get("_my_idx", 0)
    resolved = option_card_id(option, current, my_idx)
    if resolved >= 0:
        return resolved
    # CABT deck-search windows reference select.deck using area=1/index.
    index = option.get("index")
    if option.get("area") == AREA_DECK and type(index) is int:
        deck = ctx.get("_select_deck")
        if isinstance(deck, list) and 0 <= index < len(deck):
            return card_id(deck[index])
    return -1


def _missing_dragapult_colors(pokemon: dict[str, Any]) -> int:
    return int(not _has_color(pokemon, FIRE_ENERGY)) + int(not _has_color(pokemon, PSYCHIC_ENERGY))


def _damage_target_score(pokemon: dict[str, Any], amount: int, *, spread: bool = False) -> float:
    hp = remaining_hp(pokemon)
    if hp <= 0:
        return -10000
    max_hp = int(pokemon.get("maxHp") or pokemon.get("maxHP") or hp)
    existing = damage_points(pokemon)
    if hp <= amount:
        # Exact/near-exact KOs are preferred; larger bodies are generally worth more Prize tempo.
        return 1800 + min(240, max_hp) - 2 * max(0, amount - hp)
    if spread:
        # Each Phantom Dive choice places one counter. Build future 50/130/200 breakpoints.
        after = hp - 10
        threshold_bonus = max(
            0,
            190 - abs(after - 50),
            170 - abs(after - 130),
            130 - abs(after - 200),
        )
        return 900 + threshold_bonus + min(180, existing)
    # Bombs should convert immediately or create a highly concrete next attack/finisher route.
    after = hp - amount
    route_bonus = max(0, 180 - abs(after - 200), 150 - abs(after - 130), 120 - abs(after - 50))
    return 620 + route_bonus + min(180, existing)


class DragapultCinderacePolicy(ScoredPolicy):
    """Instance-aware deterministic policy for BLACK Phantom Turbo.

    Cinderace is the opening accelerator, Drakloak is the persistent draw/lineage
    engine, Dragapult is the primary attacker, Dusclops/Dusknoir convert spread
    into Prize turns, and Azelf is the one-Prize damage-reservoir finisher.
    """

    def build_context(self, obs: dict) -> dict:
        me = my_index(obs)
        opponent = 1 - me
        mine = in_play(obs, me)
        theirs = in_play(obs, opponent)
        my_active = active(obs, me)
        opp_active = active(obs, opponent)
        players = ((obs.get("current") or {}).get("players") or [{}, {}])
        player = players[me] if me < len(players) and isinstance(players[me], dict) else {}
        hand = player.get("hand") or []
        discard = player.get("discard") or []
        ids = [card_id(value) for value in mine]
        dragapults = [value for value in mine if card_id(value) == DRAGAPULT_EX]
        select = obs.get("select") if isinstance(obs.get("select"), dict) else {}
        return {
            "active_id": card_id(my_active),
            "active_serial": _serial(my_active),
            "active_energy": energy_count(my_active),
            "opp_remaining_hp": remaining_hp(opp_active),
            "opp_total_damage": sum(damage_points(value) for value in theirs),
            "opp_bench_count": len(bench(obs, opponent)),
            "my_bench_count": len(bench(obs, me)),
            "bench_energy": sum(energy_count(value) for value in bench(obs, me)),
            "dragapult_in_play": bool(dragapults),
            "dragapult_ready": any(_missing_dragapult_colors(value) == 0 for value in dragapults),
            "backup_dragapult_ready": sum(_missing_dragapult_colors(value) == 0 for value in dragapults) >= 2,
            "drakloak_count": sum(card_id(value) == DRAKLOAK for value in mine),
            "duskull_count": sum(card_id(value) == DUSKULL for value in mine),
            "dusclops_count": sum(card_id(value) == DUSCLOPS for value in mine),
            "dusknoir_count": sum(card_id(value) == DUSKNOIR for value in mine),
            "azelf_in_play": AZELF in ids,
            "cinderace_in_play": CINDERACE in ids,
            "hand_ids": tuple(card_id(value) for value in hand),
            "discard_ids": tuple(card_id(value) for value in discard),
            "effect_id": _effect_id(select),
            "select_context": select.get("context"),
            "select_type": select.get("type"),
            "_select_deck": select.get("deck") if isinstance(select.get("deck"), list) else [],
            "_current": obs.get("current"),
            "_my_idx": me,
            "_opponent_idx": opponent,
        }

    def _score_energy_target(self, card: int, target_pokemon: dict, ctx: dict) -> float:
        target = card_id(target_pokemon)
        if target in {DREEPY, DRAKLOAK, DRAGAPULT_EX}:
            missing_fire = not _has_color(target_pokemon, FIRE_ENERGY)
            missing_psychic = not _has_color(target_pokemon, PSYCHIC_ENERGY)
            if card == FIRE_ENERGY and missing_fire:
                return 1370 + 80 * int(missing_psychic)
            if card == PSYCHIC_ENERGY and missing_psychic:
                return 1360 + 80 * int(missing_fire)
            return 420  # ready Dragapult or duplicate colour: preserve Energy for the backup line.
        if target == CINDERACE:
            return 1320 if ctx["active_id"] == CINDERACE and energy_count(target_pokemon) == 0 else 410
        if target == AZELF:
            return 930 if card == PSYCHIC_ENERGY else 300
        if target in {DUSKULL, DUSCLOPS}:
            return -500 if card == FIRE_ENERGY else 210
        if target == DUSKNOIR:
            return 500 if card == PSYCHIC_ENERGY else 260
        return 350

    def score_option(self, option: dict, ctx: dict) -> float:
        current = ctx.get("_current")
        my_idx = ctx.get("_my_idx", 0)
        opponent_idx = ctx.get("_opponent_idx", 1)
        kind = option.get("type")
        card = _resolved_option_card(option, ctx)
        target_pokemon = _target_pokemon(option, current, my_idx)
        target = card_id(target_pokemon) if target_pokemon else option_target_id(option, current, my_idx)
        attack_id = option_attack_id(option)
        remaining = ctx["opp_remaining_hp"]
        effect_id = ctx["effect_id"]

        # Follow-up target windows emitted by the official engine.
        if effect_id == DRAGAPULT_EX and target_pokemon and option.get("playerIndex", opponent_idx) == opponent_idx:
            return _damage_target_score(target_pokemon, 10, spread=True)
        if effect_id == DUSCLOPS and target_pokemon and option.get("playerIndex", opponent_idx) == opponent_idx:
            return _damage_target_score(target_pokemon, 50)
        if effect_id == DUSKNOIR and target_pokemon and option.get("playerIndex", opponent_idx) == opponent_idx:
            return _damage_target_score(target_pokemon, 130)

        # Drakloak draw selection: choose the card that most advances the live route.
        if effect_id == DRAKLOAK and card >= 0:
            values = {
                DRAGAPULT_EX: 1500,
                RARE_CANDY: 1360,
                DRAKLOAK: 1280,
                CRISPIN: 1240,
                FIRE_ENERGY: 1160,
                PSYCHIC_ENERGY: 1150,
                PRIME_CATCHER: 1120,
                DUSKNOIR: 1080,
                DUSCLOPS: 980,
                LILLIE: 900,
            }
            return values.get(card, 520)

        # Crispin's multi-step window: select both colours, then attach to the individual
        # Dragapult line missing that colour. Keep the other Energy for hand attachment.
        if effect_id == CRISPIN:
            if card in {FIRE_ENERGY, PSYCHIC_ENERGY} and not target_pokemon:
                return 1300 if card == FIRE_ENERGY else 1290
            if target_pokemon:
                return self._score_energy_target(card, target_pokemon, ctx) + 100

        if kind == T_ATTACK:
            if ctx["active_id"] == DRAGAPULT_EX:
                if attack_id == DRAGAPULT_PHANTOM_DIVE:
                    return 1580 if remaining and remaining <= 200 else 1340 + 40 * min(3, ctx["opp_bench_count"])
                if attack_id == DRAGAPULT_JET_HEADBUTT:
                    return 1460 if remaining and remaining <= 70 else 650
            if ctx["active_id"] == CINDERACE and attack_id == CINDERACE_TURBO_FLARE:
                route_open = ctx["my_bench_count"] > 0 and ctx["bench_energy"] < 3
                return 1420 if route_open else 560
            if ctx["active_id"] == AZELF and attack_id == AZELF_NEUROKINESIS:
                effective = 10 + ctx["opp_total_damage"]
                return 1610 if remaining and effective >= remaining else 900 + min(500, effective)
            if ctx["active_id"] == DUSKNOIR and attack_id == DUSKNOIR_SHADOW_BIND:
                return 1400 if remaining and remaining <= 150 else 690
            return 160

        if kind == T_EVOLVE:
            # Option carries both evolution card and exact target stack.
            if card == DRAGAPULT_EX:
                return 1450 if target in {DREEPY, DRAKLOAK} else 1260
            if card == DRAKLOAK:
                return 1320  # draw engine + stable non-Candy path to the second attacker.
            if card == DUSKNOIR:
                terminal = any(0 < remaining_hp(value) <= 130 for value in in_play_from_current(current, opponent_idx))
                return 1510 if terminal else 930
            if card == DUSCLOPS:
                terminal = any(0 < remaining_hp(value) <= 50 for value in in_play_from_current(current, opponent_idx))
                return 1420 if terminal else 960
            if card == CINDERACE:
                return 760 if not ctx["cinderace_in_play"] else 260
            return 330

        if kind == T_ABILITY:
            if card == DUSKNOIR:
                terminal = any(0 < remaining_hp(value) <= 130 for value in in_play_from_current(current, opponent_idx))
                setup = ctx["dragapult_ready"] and any(130 < remaining_hp(value) <= 330 for value in in_play_from_current(current, opponent_idx))
                return 1660 if terminal else 1040 if setup else 90
            if card == DUSCLOPS:
                terminal = any(0 < remaining_hp(value) <= 50 for value in in_play_from_current(current, opponent_idx))
                setup = ctx["dragapult_ready"] and any(50 < remaining_hp(value) <= 250 for value in in_play_from_current(current, opponent_idx))
                return 1570 if terminal else 980 if setup else 80
            if card == DRAKLOAK or ctx["drakloak_count"]:
                return 1380
            return 430

        if kind == T_ENERGY:
            if target_pokemon:
                return self._score_energy_target(card, target_pokemon, ctx)
            return 300

        if kind == T_PLAY:
            if card == POFFIN:
                return 1260 if not (ctx["dragapult_in_play"] and ctx["duskull_count"] > 0) else 650
            if card == RARE_CANDY:
                has_dragapult = DRAGAPULT_EX in ctx["hand_ids"]
                has_dusknoir = DUSKNOIR in ctx["hand_ids"]
                return 1390 if has_dragapult else 1130 if has_dusknoir else 480
            if card == TERA_ORB:
                return 1240 if not ctx["dragapult_in_play"] or not ctx["backup_dragapult_ready"] else 580
            if card == POKE_PAD:
                return 1120 if not (ctx["drakloak_count"] and ctx["dusknoir_count"]) else 610
            if card == DAWN:
                return 1270 if not ctx["dragapult_in_play"] else 940
            if card == CRISPIN:
                return 1340 if not ctx["dragapult_ready"] or not ctx["backup_dragapult_ready"] else 650
            if card == LILLIE:
                return 1010
            if card == PRIME_CATCHER:
                return 1530 if ctx["dragapult_ready"] or ctx["azelf_in_play"] else 720
            if card == SWITCH:
                return 1490 if ctx["active_id"] == CINDERACE and ctx["dragapult_ready"] else 500
            if card == BOSS:
                return 1460 if ctx["dragapult_ready"] or ctx["azelf_in_play"] else 400
            if card == NIGHT_STRETCHER:
                valuable = any(value in ctx["discard_ids"] for value in (DUSKNOIR, DUSCLOPS, AZELF, DRAGAPULT_EX, FIRE_ENERGY, PSYCHIC_ENERGY))
                return 1060 if valuable else 260
            if card in {DREEPY, DUSKULL, AZELF, SCORBUNNY}:
                return 900
            return 320

        if kind == T_RETREAT:
            if ctx["active_id"] == CINDERACE and ctx["dragapult_ready"]:
                return 1510
            if ctx["active_id"] not in {DRAGAPULT_EX, AZELF} and ctx["dragapult_in_play"]:
                return 1040
            return 120

        if kind == T_END:
            return -180
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
