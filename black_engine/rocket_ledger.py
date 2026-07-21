from __future__ import annotations

from dataclasses import dataclass

from .truth import PokemonView, TruthState


TAROUNTULA = 400
SPIDOPS = 401
ARTICUNO = 414
MEWTWO_EX = 431
WOBBUFFET = 432
MURKROW = 463
ROCKET_POKEMON = frozenset({TAROUNTULA, SPIDOPS, ARTICUNO, MEWTWO_EX, WOBBUFFET, MURKROW})

GRASS_ENERGY = 1
WATER_ENERGY = 3
PSYCHIC_ENERGY = 5
TEAM_ROCKET_ENERGY = 15
BASIC_ENERGY_IDS = frozenset(range(1, 10))


def minimum_erasure_discards(remaining_hp: int) -> int | None:
    hp = max(0, int(remaining_hp))
    if hp <= 160:
        return 0
    if hp <= 220:
        return 1
    if hp <= 280:
        return 2
    return None


def energy_units(energy_ids: tuple[int, ...]) -> tuple[int, int]:
    """Return (psychic_units, total_units) under the CABT card contract."""
    rocket = sum(card == TEAM_ROCKET_ENERGY for card in energy_ids)
    psychic = sum(card == PSYCHIC_ENERGY for card in energy_ids) + 2 * rocket
    total = len(energy_ids) + rocket
    return psychic, total


def mewtwo_attack_ready(pokemon: PokemonView) -> bool:
    if pokemon.card_id != MEWTWO_EX:
        return False
    psychic, total = energy_units(pokemon.energy_ids)
    return psychic >= 2 and total >= 3


@dataclass(frozen=True)
class RocketResourceLedger:
    rocket_count: int
    bench_slots_left: int
    spidops_count: int
    mewtwo_count: int
    active_id: int
    active_mewtwo_ready: bool
    ready_benched_mewtwo: bool
    bench_energy_cards: int
    bench_basic_energy_cards: int
    bench_special_energy_cards: int
    spidops_energy_cards: int
    basic_energy_in_discard: int
    renewable_next_turn: int
    opponent_active_hp: int
    minimum_discard: int | None
    damaged_rocket_max: int
    hand_count: int
    my_prizes_remaining: int
    opponent_prizes_remaining: int

    @property
    def four_rocket_online(self) -> bool:
        return self.rocket_count >= 4

    @property
    def exact_mewtwo_terminal(self) -> bool:
        return (
            self.active_id == MEWTWO_EX
            and self.active_mewtwo_ready
            and self.four_rocket_online
            and self.minimum_discard is not None
            and self.bench_energy_cards >= self.minimum_discard
        )

    @property
    def maximum_renewable_discard(self) -> int:
        return min(2, self.bench_basic_energy_cards, self.renewable_next_turn)

    @property
    def setup_complete(self) -> bool:
        return self.four_rocket_online and (self.active_mewtwo_ready or self.ready_benched_mewtwo)


def _raw_bench_max(truth: TruthState) -> int:
    raw = truth.raw_observation if isinstance(truth.raw_observation, dict) else {}
    current = raw.get("current") if isinstance(raw.get("current"), dict) else {}
    players = current.get("players") if isinstance(current.get("players"), list) else []
    player = players[truth.actor] if 0 <= truth.actor < len(players) and isinstance(players[truth.actor], dict) else {}
    value = player.get("benchMax", 5)
    return int(value) if type(value) is int and value >= 0 else 5


def build_rocket_ledger(truth: TruthState) -> RocketResourceLedger:
    mine = truth.me.in_play
    active = truth.me.active[0] if truth.me.active else None
    bench = truth.me.bench
    spidops = [pokemon for pokemon in mine if pokemon.card_id == SPIDOPS]
    mewtwo = [pokemon for pokemon in mine if pokemon.card_id == MEWTWO_EX]
    bench_energy_ids = [card for pokemon in bench for card in pokemon.energy_ids]
    bench_basic = sum(card in BASIC_ENERGY_IDS for card in bench_energy_ids)
    basic_discard = sum(card in BASIC_ENERGY_IDS for card in truth.me.discard_ids)
    opponent_hp = truth.opponent.active[0].remaining_hp if truth.opponent.active else 0
    spidops_energy = sum(pokemon.energy_count for pokemon in spidops)
    damaged_max = max(
        (pokemon.damage for pokemon in bench if pokemon.card_id in ROCKET_POKEMON),
        default=0,
    )
    return RocketResourceLedger(
        rocket_count=sum(pokemon.card_id in ROCKET_POKEMON for pokemon in mine),
        bench_slots_left=max(0, _raw_bench_max(truth) - len(bench)),
        spidops_count=len(spidops),
        mewtwo_count=len(mewtwo),
        active_id=active.card_id if active else -1,
        active_mewtwo_ready=bool(active and mewtwo_attack_ready(active)),
        ready_benched_mewtwo=any(mewtwo_attack_ready(pokemon) for pokemon in bench),
        bench_energy_cards=len(bench_energy_ids),
        bench_basic_energy_cards=bench_basic,
        bench_special_energy_cards=len(bench_energy_ids) - bench_basic,
        spidops_energy_cards=spidops_energy,
        basic_energy_in_discard=basic_discard,
        renewable_next_turn=min(len(spidops), basic_discard + bench_basic),
        opponent_active_hp=opponent_hp,
        minimum_discard=minimum_erasure_discards(opponent_hp) if opponent_hp else None,
        damaged_rocket_max=damaged_max,
        hand_count=truth.me.hand_count,
        my_prizes_remaining=len(truth.me.prize_ids),
        opponent_prizes_remaining=len(truth.opponent.prize_ids),
    )
