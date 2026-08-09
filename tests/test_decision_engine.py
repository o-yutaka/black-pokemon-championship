from black_engine.decision_engine import DecisionEngine
from black_engine.runtime import SubmissionRuntime


class DummyPolicy:
    def set_deck(self, deck):
        self.deck = deck

    def build_context(self, obs):
        return {}

    def score_option(self, option, context):
        return float(option.get("score", 0))

    def agent(self, obs, configuration=None):
        return [0]

    def get_decision_overlay(self):
        return {}


def test_every_select_becomes_decision_point_and_preserves_position():
    policy = DummyPolicy()
    engine = DecisionEngine(policy)
    obs = {"select": {"minCount": 1, "maxCount": 1, "option": [
        {"type": 7, "score": 1},
        {"type": 8, "cardId": 11, "score": 20},
        {"type": 13, "attackId": 99, "score": 5},
    ]}}
    result = engine.evaluate(obs)
    assert result.selection == [1]
    assert [c.point.option_index for c in result.candidates] == [1, 2, 0]


def test_runtime_uses_unified_decision_engine():
    runtime = SubmissionRuntime(DummyPolicy(), [1] * 60)
    obs = {"current": {}, "select": {"minCount": 1, "maxCount": 1, "option": [
        {"type": 14, "score": 0},
        {"type": 8, "cardId": 11, "score": 10},
    ]}}
    decision = runtime.decide(obs)
    assert decision.selection == [1]
    assert decision.source == "decision_engine"
    overlay = runtime.get_decision_overlay()
    assert overlay["decisionAuthority"] == "DecisionEngine"
    assert overlay["decisionPointCount"] == 2


def test_multiselect_preserves_original_option_positions():
    engine = DecisionEngine(DummyPolicy())
    obs = {"select": {"minCount": 2, "maxCount": 2, "option": [
        {"type": 7, "score": 1},
        {"type": 7, "score": 9},
        {"type": 7, "score": 7},
    ]}}
    assert engine.evaluate(obs).selection == [1, 2]
