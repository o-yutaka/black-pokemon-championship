from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping

from .truth import TruthState

_POKEMON_CARD_IDS: set[int] | None = None


def _pokemon_card_ids() -> set[int] | None:
    """Card ids where cg.api.CardData.cardType == CardType.POKEMON (0).

    Returns None (rather than an empty set) when cg.api isn't importable,
    so callers can fall back to the untyped sampling behavior instead of
    treating "no known Pokemon" as "zero Pokemon exist".
    """
    global _POKEMON_CARD_IDS
    if _POKEMON_CARD_IDS is not None:
        return _POKEMON_CARD_IDS
    try:
        import cg.api as api
        _POKEMON_CARD_IDS = {card.cardId for card in api.all_card_data() if card.cardType == 0}
    except Exception:
        return None
    return _POKEMON_CARD_IDS


@dataclass(frozen=True)
class ArchetypeTemplate:
    name: str
    deck: tuple[int, ...]
    prior: float = 1.0

    def __post_init__(self) -> None:
        if len(self.deck) != 60:
            raise ValueError(f"{self.name}: archetype deck must contain 60 cards")
        if self.prior <= 0:
            raise ValueError("archetype prior must be positive")


@dataclass(frozen=True)
class BeliefSnapshot:
    posterior: Mapping[str, float]
    visible_opponent_cards: tuple[int, ...]
    evidence_count: int
    enabled: bool
    reason: str = ""

    @property
    def confidence(self) -> float:
        return max(self.posterior.values(), default=0.0)


@dataclass(frozen=True)
class Determinization:
    your_deck: tuple[int, ...]
    your_prize: tuple[int, ...]
    opponent_deck: tuple[int, ...]
    opponent_prize: tuple[int, ...]
    opponent_hand: tuple[int, ...]
    opponent_active: tuple[int, ...]
    archetype: str
    posterior_probability: float


class BayesianBeliefModel:
    """Bayesian archetype posterior using public evidence only.

    Templates are supplied from replay/deck evidence. With no templates the model
    is disabled and search must fail closed rather than fabricate hidden cards.
    """

    def __init__(self, templates: Iterable[ArchetypeTemplate] = ()) -> None:
        self.templates = tuple(templates)
        total = sum(template.prior for template in self.templates)
        self._posterior = {
            template.name: template.prior / total for template in self.templates
        } if total else {}
        self._evidence_count = 0

    @staticmethod
    def _visible_opponent_cards(truth: TruthState) -> tuple[int, ...]:
        opponent = truth.opponent
        opponent_index = 1 - truth.actor
        return tuple(
            [card for pokemon in opponent.in_play for card in pokemon.all_public_card_ids]
            + list(opponent.discard_ids)
            + list(BayesianBeliefModel._stadium_cards(truth, opponent_index))
            + list(BayesianBeliefModel._looking_cards(truth, opponent_index))
            + list(BayesianBeliefModel._effect_card(truth, opponent_index))
        )

    @staticmethod
    def _looking_cards(truth: TruthState, player_index: int) -> tuple[int, ...]:
        """Cards temporarily pulled out to `current.looking` (e.g. a "look
        at top N cards of your deck" effect) are real, known cards that the
        engine has already excluded from deckCount, but they are not yet in
        hand/discard/prize either. Untracked, they produced the same
        1-card-per-card "own hidden-zone mismatch" pattern as an unaccounted
        Stadium/Tool whenever a search effect was mid-resolution.
        """
        raw = truth.raw_observation if isinstance(truth.raw_observation, dict) else {}
        current = raw.get("current") if isinstance(raw.get("current"), dict) else {}
        looking = current.get("looking")
        if not isinstance(looking, list):
            return ()
        cards: list[int] = []
        for entry in looking:
            if not isinstance(entry, dict):
                continue
            if int(entry.get("playerIndex", -1)) != player_index:
                continue
            card_id = entry.get("id")
            if type(card_id) is int:
                cards.append(card_id)
        return tuple(cards)

    @staticmethod
    def _effect_card(truth: TruthState, player_index: int) -> tuple[int, ...]:
        """`select.effect` (SelectData.effect in cg.api) is "the card that is
        activating the effect currently being processed" -- e.g. a
        Supporter/Item that was just played and is mid-resolution (its own
        effect asks a follow-up question, like Team Rocket's Giovanni's
        Switch selection). It has already left hand but has not yet landed
        in discard, so it produced the same 1-card "own hidden-zone
        mismatch" pattern as an unaccounted Stadium/Tool/looking-zone card
        whenever a decision was reached mid-effect-resolution. Found via
        cg.game.visualize_data() on a live failing state, then confirmed
        `effect` is present on the plain dict observation's `select` too
        (not just the richer visualizer/dataclass view).

        `effect` is NOT always a card missing from every other zone, though:
        when a Pokemon's own Ability is resolving (e.g. Spidops' Charging
        Up), `effect` refers to that same Pokemon, which is already counted
        via in_play -- counting it again double-subtracted that card from
        the template and produced the opposite-direction mismatch (own
        deck one *short*). Only count it when its serial doesn't match an
        already-in-play Pokemon for that player.
        """
        raw = truth.raw_observation if isinstance(truth.raw_observation, dict) else {}
        select = raw.get("select") if isinstance(raw.get("select"), dict) else {}
        effect = select.get("effect")
        if not isinstance(effect, dict):
            return ()
        if int(effect.get("playerIndex", -1)) != player_index:
            return ()
        card_id = effect.get("id")
        if type(card_id) is not int:
            return ()
        effect_serial = effect.get("serial")
        current = raw.get("current") if isinstance(raw.get("current"), dict) else {}
        players = current.get("players") if isinstance(current.get("players"), list) else []
        player = players[player_index] if 0 <= player_index < len(players) else {}
        if isinstance(player, dict):
            for zone in ("active", "bench"):
                for pokemon in player.get(zone) or []:
                    if isinstance(pokemon, dict) and pokemon.get("serial") == effect_serial:
                        return ()
        return (card_id,)

    @staticmethod
    def _stadium_cards(truth: TruthState, player_index: int) -> tuple[int, ...]:
        """A played Stadium is a shared, fully public board zone -- it is
        neither in either player's in_play/discard lists, but it is a real,
        known card that must be removed from whichever player's 60-card
        template played it. Untracked (on either side), it produced a
        consistent 1-card hidden-zone accounting deficit whenever a Stadium
        (e.g. Team Rocket's Factory / Forest of Vitality) was in play.
        """
        raw = truth.raw_observation if isinstance(truth.raw_observation, dict) else {}
        current = raw.get("current") if isinstance(raw.get("current"), dict) else {}
        stadium = current.get("stadium")
        if not isinstance(stadium, list):
            return ()
        cards: list[int] = []
        for entry in stadium:
            if not isinstance(entry, dict):
                continue
            if int(entry.get("playerIndex", -1)) != player_index:
                continue
            card_id = entry.get("id")
            if type(card_id) is int:
                cards.append(card_id)
        return tuple(cards)

    @staticmethod
    def _opaque_slots(truth: TruthState, player_index: int) -> tuple[int, int]:
        """Return (face-down active count, other face-down in-play count).

        CABT represents an unrevealed setup Active as ``active: [null]`` --
        for *either* player, including the observing player's own side (the
        engine does not reveal a just-placed face-down Active back to its
        own owner in this field either). The card physically exists but is
        intentionally absent from TruthState's public Pokemon views. It
        must still be removed from the 60-card template before hand/prize/
        deck zones are sampled, and on the opponent's side the sampled
        Active identity must be supplied to cg.api.search_begin().
        """
        raw = truth.raw_observation if isinstance(truth.raw_observation, dict) else {}
        current = raw.get("current") if isinstance(raw.get("current"), dict) else {}
        players = current.get("players") if isinstance(current.get("players"), list) else []
        player = players[player_index] if 0 <= player_index < len(players) else {}
        if not isinstance(player, dict):
            return (0, 0)
        active = player.get("active") if isinstance(player.get("active"), list) else []
        bench = player.get("bench") if isinstance(player.get("bench"), list) else []
        active_nulls = sum(value is None for value in active)
        bench_nulls = sum(value is None for value in bench)
        return (active_nulls, bench_nulls)

    def update(self, truth: TruthState) -> BeliefSnapshot:
        visible = self._visible_opponent_cards(truth)
        if not self.templates:
            return BeliefSnapshot({}, visible, 0, False, "no evidence-backed archetype templates")
        evidence = Counter(visible)
        log_weights: dict[str, float] = {}
        for template in self.templates:
            counts = Counter(template.deck)
            log_likelihood = math.log(max(self._posterior.get(template.name, 1e-12), 1e-12))
            for card_id, observed in evidence.items():
                available = counts.get(card_id, 0)
                if available < observed:
                    log_likelihood += math.log(1e-12)
                else:
                    log_likelihood += observed * math.log((available + 0.25) / 60.25)
            log_weights[template.name] = log_likelihood
        maximum = max(log_weights.values())
        weights = {name: math.exp(value - maximum) for name, value in log_weights.items()}
        normalizer = sum(weights.values()) or 1.0
        self._posterior = {name: value / normalizer for name, value in weights.items()}
        self._evidence_count = sum(evidence.values())
        return BeliefSnapshot(dict(self._posterior), visible, self._evidence_count, True)

    @staticmethod
    def _remaining_cards(deck: Iterable[int], visible: Iterable[int]) -> list[int]:
        counts = Counter(int(card) for card in deck)
        for card in visible:
            counts[int(card)] -= 1
            if counts[int(card)] < 0:
                raise ValueError(f"visible card count exceeds template: card_id={card}")
        remaining: list[int] = []
        for card, count in counts.items():
            remaining.extend([card] * count)
        return remaining

    @staticmethod
    def _sample_exact(values: list[int], count: int, rng: random.Random) -> tuple[list[int], list[int]]:
        if count < 0 or count > len(values):
            raise ValueError(f"cannot sample count={count} from {len(values)} cards")
        pool = list(values)
        rng.shuffle(pool)
        return pool[:count], pool[count:]

    def sample_hidden(self, truth: TruthState, *, your_full_deck: Iterable[int], rng: random.Random) -> Determinization:
        snapshot = self.update(truth)
        if not snapshot.enabled:
            raise RuntimeError(snapshot.reason)
        names = list(snapshot.posterior)
        weights = [snapshot.posterior[name] for name in names]
        chosen_name = rng.choices(names, weights=weights, k=1)[0]
        template = next(t for t in self.templates if t.name == chosen_name)

        opponent_remaining = self._remaining_cards(template.deck, snapshot.visible_opponent_cards)
        active_nulls, other_opaque_nulls = self._opaque_slots(truth, 1 - truth.actor)
        pokemon_ids = _pokemon_card_ids() if active_nulls else None
        pokemon_pool = [c for c in opponent_remaining if pokemon_ids and c in pokemon_ids]
        if active_nulls and pokemon_ids and len(pokemon_pool) >= active_nulls:
            # cg.api.search_begin requires opponent_active to be a real
            # Pokemon card id -- the generic "any remaining card" sample
            # could otherwise pick a Trainer/Energy id by chance and get
            # rejected ("Active card must be the ID of a Pokemon card").
            active_cards, _ = self._sample_exact(pokemon_pool, active_nulls, rng)
            remaining_after_active = list(opponent_remaining)
            for card in active_cards:
                remaining_after_active.remove(card)
            other_opaque_cards, opponent_remaining = self._sample_exact(
                remaining_after_active, other_opaque_nulls, rng
            )
            opponent_active = tuple(active_cards)
        elif active_nulls:
            opaque_cards, opponent_remaining = self._sample_exact(
                opponent_remaining, active_nulls + other_opaque_nulls, rng
            )
            opponent_active = tuple(opaque_cards[:active_nulls])
        else:
            # Active already revealed -- cg.api.search_begin requires the
            # real (known) active card id here, not an empty tuple, even
            # when there is nothing left to guess.
            opaque_cards, opponent_remaining = self._sample_exact(opponent_remaining, other_opaque_nulls, rng)
            opponent_active = tuple(p.card_id for p in truth.opponent.active)
        hand, opponent_remaining = self._sample_exact(opponent_remaining, truth.opponent.hand_count, rng)
        prize, opponent_remaining = self._sample_exact(opponent_remaining, len(truth.opponent.prize_ids), rng)
        if len(opponent_remaining) != truth.opponent.deck_count:
            raise ValueError(
                "opponent hidden-zone mismatch "
                f"deck={len(opponent_remaining)} expected={truth.opponent.deck_count} "
                f"opaque_active={active_nulls} opaque_other={other_opaque_nulls}"
            )

        own_visible = (
            list(truth.me.hand_ids)
            + list(truth.me.discard_ids)
            + [card for pokemon in truth.me.in_play for card in pokemon.all_public_card_ids]
            + list(self._stadium_cards(truth, truth.actor))
            + list(self._looking_cards(truth, truth.actor))
            + list(self._effect_card(truth, truth.actor))
        )
        own_remaining = self._remaining_cards(your_full_deck, own_visible)
        # My own face-down Active/Bench slots (e.g. the pre-reveal setup
        # window) are real cards too, but unlike the opponent's face-down
        # Active there is no `your_active` parameter to search_begin -- they
        # just need to be reserved out of the remaining-deck pool so the
        # own-side hidden-zone invariant balances against deck_count.
        own_active_nulls, own_other_opaque_nulls = self._opaque_slots(truth, truth.actor)
        _, own_remaining = self._sample_exact(own_remaining, own_active_nulls + own_other_opaque_nulls, rng)
        known_prize = [value for value in truth.me.prize_ids if value is not None]
        own_remaining = self._remaining_cards(own_remaining, known_prize)
        sampled_prize, own_remaining = self._sample_exact(
            own_remaining,
            sum(value is None for value in truth.me.prize_ids),
            rng,
        )
        sampled_iter = iter(sampled_prize)
        full_prize = tuple(value if value is not None else next(sampled_iter) for value in truth.me.prize_ids)
        if len(own_remaining) != truth.me.deck_count:
            raise ValueError(f"own hidden-zone mismatch deck={len(own_remaining)} expected={truth.me.deck_count}")

        return Determinization(
            your_deck=tuple(own_remaining),
            your_prize=tuple(int(v) for v in full_prize),
            opponent_deck=tuple(opponent_remaining),
            opponent_prize=tuple(prize),
            opponent_hand=tuple(hand),
            opponent_active=opponent_active,
            archetype=chosen_name,
            posterior_probability=snapshot.posterior[chosen_name],
        )