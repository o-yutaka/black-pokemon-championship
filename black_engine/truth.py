from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


def _int(value: Any, default: int = 0) -> int:
    return int(value) if type(value) is int else default


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _card_id(value: Any) -> int:
    if type(value) is int:
        return value
    if isinstance(value, dict):
        for key in ("id", "card", "cardId", "pokemonId"):
            candidate = value.get(key)
            if type(candidate) is int:
                return candidate
    return -1


def _energy_ids(pokemon: dict) -> tuple[int, ...]:
    for key in ("energyCards", "energies", "energy"):
        values = pokemon.get(key)
        if isinstance(values, list):
            return tuple(card for card in (_card_id(v) for v in values) if card >= 0)
    return ()


def _max_hp(pokemon: dict) -> int:
    # The real cabt engine exposes `maxHp` as the ceiling and `hp` as
    # *current remaining* HP -- there is no separate damage/damageCounter
    # field. `hp` must not be treated as a max_hp fallback (see _remaining_hp).
    for key in ("maxHp", "maxHP", "HP"):
        value = pokemon.get(key)
        if type(value) in (int, float):
            return max(0, int(value))
    return 0


def _remaining_hp(pokemon: dict, max_hp: int) -> int:
    value = pokemon.get("hp")
    if type(value) in (int, float):
        return max(0, int(value))
    return max_hp


def _damage_points(pokemon: dict, max_hp: int) -> int:
    return max(0, max_hp - _remaining_hp(pokemon, max_hp))


@dataclass(frozen=True)
class PokemonView:
    card_id: int
    damage: int
    max_hp: int
    energy_ids: tuple[int, ...]
    attached_ids: tuple[int, ...] = ()
    status: tuple[str, ...] = ()
    raw_public: dict = field(default_factory=dict, compare=False, repr=False)

    @property
    def remaining_hp(self) -> int:
        return max(0, self.max_hp - self.damage) if self.max_hp else 0

    @property
    def energy_count(self) -> int:
        return len(self.energy_ids)

    @property
    def all_public_card_ids(self) -> tuple[int, ...]:
        return (self.card_id,) + self.attached_ids


@dataclass(frozen=True)
class PlayerView:
    index: int
    active: tuple[PokemonView, ...]
    bench: tuple[PokemonView, ...]
    hand_ids: tuple[int, ...]
    hand_count: int
    discard_ids: tuple[int, ...]
    prize_ids: tuple[int | None, ...]
    deck_count: int
    supporter_played: bool
    retreated: bool
    energy_attached: bool

    @property
    def in_play(self) -> tuple[PokemonView, ...]:
        return self.active + self.bench


@dataclass(frozen=True)
class LegalOption:
    index: int
    action_type: int
    card_id: int
    target_id: int
    attack_id: int
    label: str
    raw: dict = field(compare=False, repr=False)

    @property
    def signature(self) -> str:
        return f"{self.action_type}:{self.card_id}:{self.target_id}:{self.attack_id}:{self.label[:48]}"


@dataclass(frozen=True)
class TruthState:
    actor: int
    turn: int
    result: int
    players: tuple[PlayerView, PlayerView]
    options: tuple[LegalOption, ...]
    min_count: int
    max_count: int
    select_type: int
    select_context: int
    logs: tuple[Any, ...]
    raw_observation: dict = field(compare=False, repr=False)

    @property
    def me(self) -> PlayerView:
        return self.players[self.actor]

    @property
    def opponent(self) -> PlayerView:
        return self.players[1 - self.actor]

    @property
    def terminal(self) -> bool:
        return self.result in (0, 1)

    def information_set_key(self) -> tuple:
        def poke_key(p: PokemonView) -> tuple:
            return (p.card_id, p.damage, p.max_hp, p.energy_ids, p.status)

        return (
            self.actor,
            self.turn,
            self.result,
            tuple(poke_key(p) for p in self.me.active),
            tuple(poke_key(p) for p in self.me.bench),
            self.me.hand_ids,
            self.me.deck_count,
            tuple(poke_key(p) for p in self.opponent.active),
            tuple(poke_key(p) for p in self.opponent.bench),
            self.opponent.hand_count,
            self.opponent.deck_count,
            tuple(option.signature for option in self.options),
        )


def _attached_ids(pokemon: dict, energy_ids: tuple[int, ...]) -> tuple[int, ...]:
    values: list[int] = list(energy_ids)
    for key in (
        "tool", "pokemonTool", "attachedTool", "toolCard",
        "evolutionCards", "cards", "stack", "under", "preEvolution",
    ):
        raw = pokemon.get(key)
        items = raw if isinstance(raw, list) else [raw] if raw is not None else []
        for item in items:
            card = _card_id(item)
            if card >= 0 and card != _card_id(pokemon) and card not in values:
                values.append(card)
    return tuple(values)


def _pokemon_view(value: Any) -> PokemonView | None:
    if not isinstance(value, dict):
        return None
    card = _card_id(value)
    if card < 0:
        return None
    status_names = ("poisoned", "burned", "asleep", "paralyzed", "confused")
    status = tuple(name for name in status_names if bool(value.get(name)))
    energy_ids = _energy_ids(value)
    max_hp = _max_hp(value)
    return PokemonView(
        card_id=card,
        damage=_damage_points(value, max_hp),
        max_hp=max_hp,
        energy_ids=energy_ids,
        attached_ids=_attached_ids(value, energy_ids),
        status=status,
        raw_public=dict(value),
    )


def _ids(values: Iterable[Any]) -> tuple[int, ...]:
    return tuple(card for card in (_card_id(v) for v in values) if card >= 0)


def _player_view(value: Any, index: int, actor: int) -> PlayerView:
    player = value if isinstance(value, dict) else {}
    active = tuple(p for p in (_pokemon_view(v) for v in _list(player.get("active"))) if p)
    bench = tuple(p for p in (_pokemon_view(v) for v in _list(player.get("bench"))) if p)
    raw_hand = _list(player.get("hand"))
    hand_ids = _ids(raw_hand) if index == actor else ()
    hand_count = _int(player.get("handCount"), len(raw_hand))
    raw_prize = _list(player.get("prize"))
    prize_ids = tuple(None if v is None else (_card_id(v) if _card_id(v) >= 0 else None) for v in raw_prize)
    return PlayerView(
        index=index,
        active=active,
        bench=bench,
        hand_ids=hand_ids,
        hand_count=hand_count,
        discard_ids=_ids(_list(player.get("discard"))),
        prize_ids=prize_ids,
        deck_count=_int(player.get("deckCount"), len(_list(player.get("deck")))),
        supporter_played=bool(player.get("supporterPlayed", False)),
        retreated=bool(player.get("retreated", player.get("retreatUsed", False))),
        energy_attached=bool(player.get("energyAttached", player.get("energyPlayed", False))),
    )


def _label(option: dict) -> str:
    values: list[str] = []
    for key in ("name", "text", "label", "attackName", "moveName"):
        value = option.get(key)
        if isinstance(value, str):
            values.append(value)
    attack = option.get("attack")
    if isinstance(attack, dict):
        for key in ("name", "text"):
            value = attack.get(key)
            if isinstance(value, str):
                values.append(value)
    return " ".join(values).strip().lower()


def _option(value: Any, index: int) -> LegalOption:
    raw = value if isinstance(value, dict) else {}
    attack = raw.get("attack")
    attack_id = -1
    if isinstance(attack, dict):
        attack_id = _int(attack.get("attackId"), _int(attack.get("id"), -1))
    if attack_id < 0:
        attack_id = _int(raw.get("attackId"), -1)
    target = -1
    for key in ("target", "pokemon", "to", "selectPokemon"):
        target = _card_id(raw.get(key))
        if target >= 0:
            break
    card = -1
    for key in ("card", "cardId", "id"):
        card = _card_id(raw.get(key))
        if card >= 0:
            break
    return LegalOption(
        index=index,
        action_type=_int(raw.get("type"), -1),
        card_id=card,
        target_id=target,
        attack_id=attack_id,
        label=_label(raw),
        raw=raw,
    )


def build_truth_state(obs: dict) -> TruthState:
    if not isinstance(obs, dict):
        raise TypeError("observation must be a dict")
    current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
    actor = _int(current.get("yourIndex"), 0)
    if actor not in (0, 1):
        raise ValueError(f"invalid current.yourIndex={actor!r}")
    raw_players = _list(current.get("players"))
    players = tuple(
        _player_view(raw_players[index] if index < len(raw_players) else {}, index, actor)
        for index in (0, 1)
    )
    select = obs.get("select") if isinstance(obs.get("select"), dict) else {}
    options = tuple(_option(value, index) for index, value in enumerate(_list(select.get("option"))))
    minimum = max(0, _int(select.get("minCount"), 1))
    maximum = max(0, _int(select.get("maxCount"), 1))
    return TruthState(
        actor=actor,
        turn=_int(current.get("turn"), _int(current.get("turnCount"), 0)),
        result=_int(current.get("result"), -1),
        players=players,  # type: ignore[arg-type]
        options=options,
        min_count=minimum,
        max_count=maximum,
        select_type=_int(select.get("type"), -1),
        select_context=_int(select.get("context"), -1),
        logs=tuple(_list(obs.get("logs"))),
        raw_observation=obs,
    )
