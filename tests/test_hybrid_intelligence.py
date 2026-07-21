from __future__ import annotations

from black_engine.belief import ArchetypeTemplate, BayesianBeliefModel, Determinization
from black_engine.guards import MewtwoFourRocketGuard
from black_engine.hybrid import HybridPolicy
from black_engine.ismcts import InformationSetMCTS, SearchFrame
from black_engine.rl_prior import TabularQPrior
from black_engine.truth import build_truth_state
from black_lab import build_policy


def pokemon(card_id, *, hp=200, damage=0, energy=(), tool=None):
    value = {"id": card_id, "hp": hp, "damage": damage, "energyCards": list(energy)}
    if tool is not None:
        value["tool"] = tool
    return value


def observation(*, rocket_count=4, options=None, opponent_hand=None):
    mine = [pokemon(431, hp=280, energy=(15, 5, 5), tool=1159)]
    mine.extend(pokemon(card) for card in [400, 401, 414][: max(0, rocket_count - 1)])
    opponent_hand = opponent_hand if opponent_hand is not None else [999, 998, 997]
    return {
        "current": {
            "yourIndex": 0,
            "turn": 3,
            "result": -1,
            "players": [
                {
                    "active": [mine[0]],
                    "bench": mine[1:],
                    "hand": [1, 2, 3],
                    "handCount": 3,
                    "discard": [],
                    "prize": [None] * 6,
                    "deckCount": 47,
                },
                {
                    "active": [pokemon(700, hp=220)],
                    "bench": [],
                    "hand": opponent_hand,
                    "handCount": len(opponent_hand),
                    "discard": [],
                    "prize": [None] * 6,
                    "deckCount": 50,
                },
            ],
        },
        "logs": [],
        "select": {
            "type": 1,
            "context": 0,
            "minCount": 1,
            "maxCount": 1,
            "option": options or [
                {"type": 13, "name": "Erasure Ball"},
                {"type": 14, "name": "End"},
            ],
        },
    }


def test_truth_state_hides_opponent_hand_and_tracks_attachments():
    truth = build_truth_state(observation(opponent_hand=[101, 102, 103]))
    assert truth.me.hand_ids == (1, 2, 3)
    assert truth.opponent.hand_ids == ()
    assert truth.opponent.hand_count == 3
    assert set(truth.me.active[0].attached_ids) == {15, 5, 1159}


def test_mewtwo_guard_rejects_attack_before_four_rocket():
    truth = build_truth_state(observation(rocket_count=3))
    vote = MewtwoFourRocketGuard().evaluate(truth, truth.options[0])
    assert vote.hard_reject is True
    assert "<4" in vote.reason


def test_hybrid_guard_overrides_high_base_attack_score():
    base = build_policy("mewtwo_spidops")
    policy = HybridPolicy("mewtwo_spidops", base)
    policy.set_deck(list(range(60)))
    assert policy.agent(observation(rocket_count=3)) == [1]


def test_bayesian_posterior_moves_to_matching_template():
    deck_a = tuple([700] * 4 + list(range(56)))
    deck_b = tuple([701] * 4 + list(range(100, 156)))
    model = BayesianBeliefModel([ArchetypeTemplate("A", deck_a), ArchetypeTemplate("B", deck_b)])
    truth = build_truth_state(observation())
    snapshot = model.update(truth)
    assert snapshot.enabled is True
    assert snapshot.posterior["A"] > snapshot.posterior["B"]


def test_rl_prior_learns_and_round_trips(tmp_path):
    prior = TabularQPrior()
    prior.update_episode([("s0", "a0", 0.0), ("s1", "a1", 1.0)], gamma=1.0, alpha=1.0)
    assert prior.q_values["s0|a0"] == 1.0
    path = tmp_path / "prior.json"
    prior.save(path)
    loaded = TabularQPrior.load(path)
    assert loaded.trained is True
    assert loaded.q_values == prior.q_values


class FakeAdapter:
    def __init__(self):
        self.next_id = 1

    def begin(self, truth, determinization):
        frame = SearchFrame(self.next_id, truth.raw_observation, -1)
        self.next_id += 1
        return frame

    def step(self, search_id, selection):
        result = 0 if selection == [0] else 1
        obs = {
            "current": {"yourIndex": 0, "result": result, "players": [{}, {}]},
            "select": {"minCount": 0, "maxCount": 0, "option": []},
        }
        frame = SearchFrame(self.next_id, obs, result)
        self.next_id += 1
        return frame

    def release(self, search_id):
        return None

    def end(self):
        return None


class FixedBelief:
    def update(self, truth):
        return type("Snapshot", (), {"enabled": True, "reason": "", "confidence": 1.0})()

    def sample_hidden(self, truth, *, your_full_deck, rng):
        return Determinization(
            your_deck=tuple([1] * truth.me.deck_count),
            your_prize=tuple([1] * len(truth.me.prize_ids)),
            opponent_deck=tuple([2] * truth.opponent.deck_count),
            opponent_prize=tuple([2] * len(truth.opponent.prize_ids)),
            opponent_hand=tuple([2] * truth.opponent.hand_count),
            opponent_active=(),
            archetype="fake",
            posterior_probability=1.0,
        )


def test_ismcts_prefers_winning_root_action():
    truth = build_truth_state(observation())
    search = InformationSetMCTS(
        FakeAdapter(),
        FixedBelief(),
        simulations=20,
        time_budget_ms=1000,
        rollout_depth=1,
        seed=7,
    )
    result = search.evaluate(truth, your_full_deck=list(range(60)))
    assert result.enabled is True
    assert result.value_for(0).mean_value > result.value_for(1).mean_value
    assert result.value_for(0).visits > result.value_for(1).visits
