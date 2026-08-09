from black_engine.decision_authority import DecisionAuthority
from black_engine.decision_point import build_decision_points


class DummyPolicy:
    def agent(self, obs, configuration=None):
        return [1]


def test_every_select_is_normalized_without_reordering_positions():
    obs = {"select": {"minCount": 1, "maxCount": 1, "option": [
        {"type": 7, "cardId": 10},
        {"type": 8, "cardId": 11, "target": 12},
        {"type": 13, "attackId": 99},
    ]}}
    points = build_decision_points(obs)
    assert [p.option_index for p in points] == [0, 1, 2]
    assert points[1].action_type == 8
    assert points[1].card_id == 11
    assert points[1].target_id == 12


def test_authority_preserves_canonical_policy_by_default():
    obs = {"select": {"minCount": 1, "maxCount": 1, "option": [
        {"type": 14},
        {"type": 8, "cardId": 11},
    ]}}
    result = DecisionAuthority(DummyPolicy()).decide(obs)
    assert result.selection == [1]
    assert result.source == "canonical_policy"
    assert result.hros_verified is False
