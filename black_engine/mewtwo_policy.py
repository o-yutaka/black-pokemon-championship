from __future__ import annotations

from typing import Any

from black_lab import ScoredPolicy, normalize_selection

from .official_observation import normalize_official_observation
from .rocket_ledger import (
    ARTICUNO,
    BASIC_ENERGY_IDS,
    GRASS_ENERGY,
    MEWTWO_EX,
    MURKROW,
    PSYCHIC_ENERGY,
    ROCKET_POKEMON,
    SPIDOPS,
    TAROUNTULA,
    TEAM_ROCKET_ENERGY,
    WATER_ENERGY,
    WOBBUFFET,
    RocketResourceLedger,
    build_rocket_ledger,
    energy_units,
)
from .truth import LegalOption, PokemonView, TruthState, build_truth_state


T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14

CTX_SETUP_ACTIVE = 1
CTX_SETUP_BENCH = 2
CTX_SWITCH = 3
CTX_TO_ACTIVE = 4
CTX_TO_HAND = 7
CTX_DISCARD = 8
CTX_DAMAGE_COUNTER = 13
CTX_DAMAGE_COUNTER_ANY = 14
CTX_DAMAGE = 15
CTX_REMOVE_DAMAGE = 16
CTX_EVOLVES_FROM = 18
CTX_EVOLVES_TO = 19

BUG_CATCHING_SET = 1094
NIGHT_STRETCHER = 1097
ENERGY_SEARCH = 1119
ROCKET_TRANSCEIVER = 1134
POKE_PAD = 1152
HEROES_CAPE = 1159
BRAVE_BANGLE = 1175
ARIANA = 1216
ARCHER = 1217
GIOVANNI = 1218
PETREL = 1219
PROTON = 1220
LILLIE = 1227
ROCKET_FACTORY = 1257

ROCKET_SUPPORTERS = frozenset({ARIANA, ARCHER, GIOVANNI, PETREL, PROTON})

SPIDOPS_ROCKET_RUSH = 560
ARTICUNO_DARK_FROST = 583
MEWTWO_ERASURE_BALL = 608
WOBBUFFET_ROCKET_MIRROR = 609
WOBBUFFET_HEADBUTT = 610
MURKROW_DECEIT = 652
MURKROW_TORMENT = 653


def _card_id(value: Any) -> int:
    if type(value) is int:
        return value
    if isinstance(value, dict):
        for key in ("id", "card", "cardId", "pokemonId"):
            card = value.get(key)
            if type(card) is int:
                return card
    return -1


def _current_stadium_id(truth: TruthState) -> int:
    raw = truth.raw_observation
    current = raw.get("current") if isinstance(raw, dict) and isinstance(raw.get("current"), dict) else {}
    stadium = current.get("stadium") if isinstance(current.get("stadium"), list) else []
    return _card_id(stadium[0]) if stadium else -1


def _find_pokemon(truth: TruthState, card_id: int) -> PokemonView | None:
    return next((pokemon for pokemon in truth.me.in_play if pokemon.card_id == card_id), None)


def _find_target(truth: TruthState, option: LegalOption) -> PokemonView | None:
    if option.target_id < 0:
        return None
    return next((pokemon for pokemon in truth.me.in_play if pokemon.card_id == option.target_id), None)


def _resolve_option(raw: dict, truth: TruthState) -> LegalOption | None:
    for option in truth.options:
        if option.raw is raw or option.raw == raw:
            return option
    return None


class MewtwoChampionshipPolicy(ScoredPolicy):
    """Strong deterministic prior for Team Rocket Mewtwo/Spidops."""

    def build_context(self, obs: dict) -> dict:
        truth = build_truth_state(normalize_official_observation(obs))
        ledger = build_rocket_ledger(truth)
        active = truth.me.active[0] if truth.me.active else None
        return {
            "truth": truth,
            "ledger": ledger,
            "active": active,
            "stadium_id": _current_stadium_id(truth),
            "hand_ids": set(truth.me.hand_ids),
            "rocket_supporter_in_hand": any(card in ROCKET_SUPPORTERS for card in truth.me.hand_ids),
        }

    def _selection_score(self, option: LegalOption, truth: TruthState, ledger: RocketResourceLedger) -> float:
        card = option.card_id
        context = truth.select_context

        if context == CTX_SETUP_ACTIVE:
            return {MURKROW: 1000, ARTICUNO: 940, TAROUNTULA: 860, WOBBUFFET: 700, MEWTWO_EX: 520}.get(card, 100)

        if context == CTX_SETUP_BENCH:
            return {
                MEWTWO_EX: 1250 if ledger.mewtwo_count == 0 else 730,
                TAROUNTULA: 1180 if ledger.spidops_count == 0 else 920,
                MURKROW: 1040,
                ARTICUNO: 920,
                WOBBUFFET: 620,
            }.get(card, 100)

        if context in {CTX_SWITCH, CTX_TO_ACTIVE}:
            pokemon = _find_pokemon(truth, card)
            if pokemon and pokemon.card_id == MEWTWO_EX:
                psychic, total = energy_units(pokemon.energy_ids)
                if ledger.four_rocket_online and psychic >= 2 and total >= 3:
                    return 1500
            if card == MURKROW and not ledger.four_rocket_online:
                return 980
            if card == ARTICUNO:
                return 860
            if card == SPIDOPS:
                damage = 30 * ledger.rocket_count
                return 1200 if damage >= ledger.opponent_active_hp > 0 else 800
            return 400

        if context == CTX_TO_HAND:
            return self._search_value(card, truth, ledger)

        if context == CTX_DISCARD:
            score = 0.0
            if card in BASIC_ENERGY_IDS:
                score += 300
            elif card == TEAM_ROCKET_ENERGY:
                score -= 500
            if option.target_id == SPIDOPS:
                score += 220
            elif option.target_id == MEWTWO_EX:
                score -= 1000
            elif option.target_id in {ARTICUNO, WOBBUFFET, MURKROW}:
                score += 40
            return score

        if context in {CTX_DAMAGE_COUNTER, CTX_DAMAGE_COUNTER_ANY, CTX_DAMAGE, CTX_REMOVE_DAMAGE}:
            pokemon = _find_pokemon(truth, card)
            return float(pokemon.damage if pokemon and pokemon.card_id in ROCKET_POKEMON else 0)

        if context in {CTX_EVOLVES_FROM, CTX_EVOLVES_TO}:
            return 1200 if card in {TAROUNTULA, SPIDOPS} else 100

        return self._search_value(card, truth, ledger)

    def _search_value(self, card: int, truth: TruthState, ledger: RocketResourceLedger) -> float:
        if card == MEWTWO_EX:
            return 1400 if ledger.mewtwo_count == 0 else 760
        if card == SPIDOPS:
            return 1360 if ledger.spidops_count == 0 else 1040
        if card == TAROUNTULA:
            return 1320 if ledger.spidops_count == 0 else 900
        if card == MURKROW:
            return 1240 if ledger.rocket_count < 4 else 650
        if card == ARTICUNO:
            return 1120 if ledger.rocket_count < 4 else 620
        if card == WOBBUFFET:
            return 1180 if ledger.damaged_rocket_max >= ledger.opponent_active_hp > 0 else 500
        if card == PROTON:
            return 1500 if truth.turn <= 1 or ledger.rocket_count < 4 else 360
        if card == GIOVANNI:
            return 1450 if ledger.ready_benched_mewtwo and ledger.four_rocket_online else 780
        if card == ARIANA:
            return 1320 if ledger.hand_count <= 4 else 850
        if card == PETREL:
            return 1180
        if card == ARCHER:
            return 1050
        if card == ROCKET_FACTORY:
            return 1300 if _current_stadium_id(truth) != ROCKET_FACTORY else 200
        if card == TEAM_ROCKET_ENERGY:
            return 1380 if not ledger.active_mewtwo_ready else 620
        if card == PSYCHIC_ENERGY:
            return 1080 if not ledger.active_mewtwo_ready else 560
        if card == GRASS_ENERGY:
            return 1120 if ledger.spidops_energy_cards < max(1, ledger.spidops_count) else 600
        if card == WATER_ENERGY:
            return 650
        if card in {BUG_CATCHING_SET, ROCKET_TRANSCEIVER, POKE_PAD, ENERGY_SEARCH}:
            return 980
        return 300

    def score_option(self, option: dict, ctx: dict) -> float:
        truth: TruthState = ctx["truth"]
        ledger: RocketResourceLedger = ctx["ledger"]
        legal = _resolve_option(option, truth)
        if legal is None:
            return -500.0

        if legal.action_type not in {T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END}:
            return self._selection_score(legal, truth, ledger)

        card = legal.card_id
        target = legal.target_id

        if legal.action_type == T_ATTACK:
            active = ctx.get("active")
            active_id = active.card_id if active else -1
            remaining = ledger.opponent_active_hp
            if active_id == MEWTWO_EX and legal.attack_id == MEWTWO_ERASURE_BALL:
                if not ledger.four_rocket_online or not ledger.active_mewtwo_ready:
                    return -10000
                needed = ledger.minimum_discard
                if needed is not None and ledger.bench_energy_cards >= needed:
                    return 1700 - 20 * needed + 30 * min(2, ledger.maximum_renewable_discard)
                return 900 if remaining > 280 else 620
            if active_id == SPIDOPS and legal.attack_id == SPIDOPS_ROCKET_RUSH:
                damage = 30 * ledger.rocket_count
                return 1550 if damage >= remaining > 0 else 820 + damage
            if active_id == WOBBUFFET:
                if legal.attack_id == WOBBUFFET_ROCKET_MIRROR:
                    return 1600 if ledger.damaged_rocket_max >= remaining > 0 else 760 + ledger.damaged_rocket_max
                if legal.attack_id == WOBBUFFET_HEADBUTT:
                    return 1450 if 70 >= remaining > 0 else 720
            if active_id == ARTICUNO and legal.attack_id == ARTICUNO_DARK_FROST:
                damage = 120 if TEAM_ROCKET_ENERGY in active.energy_ids else 60
                return 1480 if damage >= remaining > 0 else 760 + damage
            if active_id == MURKROW:
                if legal.attack_id == MURKROW_DECEIT:
                    return 1080 if ledger.rocket_count < 4 or not truth.me.supporter_played else 380
                if legal.attack_id == MURKROW_TORMENT:
                    return 820
            return 120

        if legal.action_type == T_EVOLVE:
            return 1320 if card == SPIDOPS else 300

        if legal.action_type == T_ABILITY:
            if card == SPIDOPS:
                return 1320 if ledger.basic_energy_in_discard > 0 else 720
            if card == ROCKET_FACTORY:
                return 1220 if truth.me.supporter_played else 320
            return 500

        if legal.action_type == T_ENERGY:
            pokemon = _find_target(truth, legal)
            energy = card
            if target == MEWTWO_EX:
                psychic, total = energy_units(pokemon.energy_ids if pokemon else ())
                if energy == TEAM_ROCKET_ENERGY and psychic < 2:
                    return 1500
                if energy == PSYCHIC_ENERGY and psychic < 2:
                    return 1260
                if total < 3:
                    return 1210
                return 430
            if target == SPIDOPS:
                count = pokemon.energy_count if pokemon else 0
                if energy == GRASS_ENERGY and count < 2:
                    return 1260 - 80 * count
                if energy in BASIC_ENERGY_IDS and count < 2:
                    return 960 - 60 * count
                if energy == TEAM_ROCKET_ENERGY:
                    return 280
                return 620
            if target == ARTICUNO:
                ids = pokemon.energy_ids if pokemon else ()
                if energy == WATER_ENERGY and WATER_ENERGY not in ids:
                    return 1060
                if energy == TEAM_ROCKET_ENERGY and WATER_ENERGY in ids:
                    return 940
                return 480
            if target == MURKROW and energy == TEAM_ROCKET_ENERGY and ledger.rocket_count < 4:
                return 920
            if target == WOBBUFFET and energy == TEAM_ROCKET_ENERGY and ledger.damaged_rocket_max > 0:
                return 880
            if energy == TEAM_ROCKET_ENERGY and target not in ROCKET_POKEMON:
                return -10000
            return 420

        if legal.action_type == T_PLAY:
            if card in ROCKET_POKEMON:
                return self._search_value(card, truth, ledger)
            if card == PROTON:
                return 1540 if truth.turn <= 1 or ledger.rocket_count < 4 else 260
            if card == ROCKET_FACTORY:
                return 1380 if ctx["stadium_id"] != ROCKET_FACTORY and not truth.me.supporter_played else 600
            if card == ROCKET_TRANSCEIVER:
                return 1320 if not truth.me.supporter_played else 520
            if card == ARIANA:
                return 1280 if ledger.hand_count <= 4 or ctx["stadium_id"] == ROCKET_FACTORY else 820
            if card == GIOVANNI:
                if ledger.ready_benched_mewtwo and ledger.four_rocket_online:
                    return 1510
                if ledger.active_id == MEWTWO_EX and ledger.exact_mewtwo_terminal:
                    return 1200
                return 650
            if card == ARCHER:
                return 1080
            if card == PETREL:
                return 1120
            if card == LILLIE:
                return 1260 if ledger.hand_count <= 4 or ledger.my_prizes_remaining == 6 else 760
            if card == BUG_CATCHING_SET:
                return 1220 if ledger.spidops_count == 0 or ledger.spidops_energy_cards < 2 else 700
            if card == POKE_PAD:
                return 1210 if ledger.rocket_count < 4 or ledger.spidops_count == 0 else 660
            if card == ENERGY_SEARCH:
                return 1120 if not ledger.active_mewtwo_ready else 620
            if card == NIGHT_STRETCHER:
                return 920 if any(value in ROCKET_POKEMON or value in BASIC_ENERGY_IDS for value in truth.me.discard_ids) else 400
            if card == HEROES_CAPE:
                return 1430 if target == MEWTWO_EX else 620
            if card == BRAVE_BANGLE:
                return 980 if target in {SPIDOPS, WOBBUFFET, ARTICUNO, MURKROW} else 350
            return 350

        if legal.action_type == T_RETREAT:
            if ledger.ready_benched_mewtwo and ledger.four_rocket_online and ledger.active_id != MEWTWO_EX:
                return 1500
            if ledger.active_id == MEWTWO_EX and not ledger.active_mewtwo_ready:
                return 980
            return 160

        if legal.action_type == T_END:
            if any(candidate.action_type in {T_ATTACK, T_EVOLVE, T_ABILITY, T_ENERGY} for candidate in truth.options):
                return -900
            return 0

        return 0

    def choose_multi(self, options: list, context: dict, minimum: int, maximum: int) -> list[int]:
        truth: TruthState = context["truth"]
        ledger: RocketResourceLedger = context["ledger"]
        legal_options = list(truth.options)

        if truth.select_context == CTX_SETUP_BENCH:
            target_count = min(maximum, max(minimum, max(0, 4 - ledger.rocket_count)))
            scored = sorted(
                ((self._selection_score(option, truth, ledger), option.index) for option in legal_options),
                reverse=True,
            )
            return [index for _, index in scored[:target_count]]

        energy_options = [
            option for option in legal_options
            if option.card_id in BASIC_ENERGY_IDS or option.card_id == TEAM_ROCKET_ENERGY
        ]
        if (
            ledger.active_id == MEWTWO_EX
            and truth.select_context == CTX_DISCARD
            and maximum <= 2
            and energy_options
        ):
            needed = ledger.minimum_discard
            count = 0 if needed is None else min(maximum, max(minimum, needed))
            scored = sorted(
                ((self._selection_score(option, truth, ledger), option.index) for option in energy_options),
                reverse=True,
            )
            return [index for _, index in scored[:count]]

        return super().choose_multi(options, context, minimum, maximum)

    def agent(self, obs: dict | None, configuration=None):
        raw = super().agent(obs, configuration)
        return normalize_selection(obs, raw) if isinstance(obs, dict) and obs.get("select") is not None else raw


def build_mewtwo_policy() -> MewtwoChampionshipPolicy:
    return MewtwoChampionshipPolicy()
