from black_engine.submission_runtime import OfficialHybridRuntime, deterministic_fallback, legalize_selection


def obs(minimum=1, maximum=1, count=3):
    return {"select": {"minCount": minimum, "maxCount": maximum, "option": [{} for _ in range(count)]}}


class Policy:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.deck = None

    def set_deck(self, deck):
        self.deck = list(deck)

    def agent(self, observation, configuration=None):
        if self.error:
            raise self.error
        return self.value


def test_legalize_exact_official_contract():
    assert legalize_selection(obs(), 2) == [2]
    assert legalize_selection(obs(), [1]) == [1]
    assert legalize_selection(obs(), [3]) is None
    assert legalize_selection(obs(1, 2), [0, 0]) is None
    assert legalize_selection(obs(0, 2), []) == []


def test_hybrid_valid_selection_wins():
    runtime = OfficialHybridRuntime(Policy([1]), Policy([2]), [7] * 60)
    decision = runtime.decide(obs())
    assert decision.selection == [1]
    assert decision.source == "hybrid"


def test_invalid_hybrid_falls_back_to_base():
    runtime = OfficialHybridRuntime(Policy([99]), Policy([2]), [7] * 60)
    decision = runtime.decide(obs())
    assert decision.selection == [2]
    assert decision.source == "base_fallback"
    assert decision.error == "invalid_selection"


def test_double_failure_uses_legal_deterministic_fallback():
    runtime = OfficialHybridRuntime(Policy(error=RuntimeError("hybrid")), Policy([99]), [7] * 60)
    decision = runtime.decide(obs(1, 1, 4))
    assert decision.selection == [3]
    assert decision.source == "deterministic_fallback"


def test_initial_observation_returns_deck():
    deck = list(range(60))
    runtime = OfficialHybridRuntime(Policy(), Policy(), deck)
    assert runtime.agent({"select": None}) == deck


def test_deterministic_fallback_respects_zero_minimum():
    assert deterministic_fallback(obs(0, 3, 4)) == []
