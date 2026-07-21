from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping

from .truth import TruthState


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

    Templates must come from replay/deck evidence. With no templates the model
    disables search rather than fabricating hidden cards.
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
        return tuple([pokemon.card_id for pokemon in opponent.in_play] + list(opponent.discard_ids))

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
        hand, opponent_remaining = self._sample_exact(opponent_remaining, truth.opponent.hand_count, rng)
        prize, opponent_remaining = self._sample_exact(opponent_remaining, len(truth.opponent.prize_ids), rng)
        if len(opponent_remaining) != truth.opponent.deck_count:
            raise ValueError(f"opponent hidden-zone mismatch deck={len(opponent_remaining)} expected={truth.opponent.deck_count}")

        own_visible = list(truth.me.hand_ids) + list(truth.me.discard_ids) + [p.card_id for p in truth.me.in_play]
        own_remaining = self._remaining_cards(your_full_deck, own_visible)
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
            opponent_active=(),
            archetype=chosen_name,
            posterior_probability=snapshot.posterior[chosen_name],
        )
