from black_engine.worldline.energy import count_effective_units
from black_engine.worldline.judge import CausalJudge
from black_engine.worldline.model import CandidatePlan, WorldlineResult


def _result(index: int, **kwargs):
    return WorldlineResult(CandidatePlan(str(index), "test", index), **kwargs)


def test_immediate_loss_is_rejected_before_expected_value():
    judge = CausalJudge()
    losing = _result(0, immediate_loss=True, guaranteed_win=True, opponent_pain=999)
    safe = _result(1, our_attacks_to_win=3, opponent_attacks_to_win=2)
    assert judge.choose([losing, safe]) is safe


def test_terminal_win_dominates_non_terminal_plan():
    judge = CausalJudge()
    terminal = _result(0, guaranteed_win=True)
    setup = _result(1, our_attacks_to_win=1, opponent_pain=999)
    assert judge.choose([setup, terminal]) is terminal


def test_physical_energy_cards_are_distinct_from_units():
    cards = (5, 999)
    assert len(cards) == 2
    assert count_effective_units(cards, frozenset({999})) == 3
