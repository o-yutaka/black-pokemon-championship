from collections import Counter

from black_engine.dragapult_worldline import DragapultWorldlinePolicy
from black_engine.policy import BOSS, CRISPIN, DRAKLOAK, DUSKNOIR, SWITCH, T_ABILITY, T_EVOLVE, T_PLAY, T_RETREAT


def context(**overrides):
    value = {
        "me": 0,
        "opp": 1,
        "current": {"players": [{}, {}]},
        "select": {"option": []},
        "effect": -1,
        "context": -1,
        "active_id": 666,
        "opp_hp": 300,
        "opp_damage": 0,
        "opp_bench": 2,
        "bench_slots": 2,
        "deck_count": 20,
        "hand_ids": (),
        "discard_ids": (),
        "counts": Counter(),
        "mine": [],
        "theirs": [{"id": 999, "hp": 300, "maxHp": 300}],
        "dragapult_lines": [{"id": 121, "energyCards": []}],
        "dragapult_ready": False,
        "ready_count": 0,
        "azelf_ready": False,
        "our_prizes": 4,
        "opponent_prizes": 4,
    }
    value.update(overrides)
    return value


def test_bomb_is_rejected_when_it_gives_opponent_final_prize():
    policy = DragapultWorldlinePolicy()
    ctx = context(opponent_prizes=1, theirs=[{"id": 999, "hp": 100, "maxHp": 100}])
    result = policy._plan_for_option(0, {"type": T_ABILITY, "cardId": DUSKNOIR}, ctx)
    assert result.immediate_loss is True


def test_drakloak_ability_precedes_same_select_evolution():
    policy = DragapultWorldlinePolicy()
    options = [
        {"type": T_EVOLVE, "cardId": 121},
        {"type": T_ABILITY, "cardId": DRAKLOAK},
    ]
    ctx = context(select={"option": options})
    assert policy.choose_single(options, ctx) == 1
    assert policy.last_runner_id == "DRAKLOAK_BEFORE_EVOLVE"


def test_crispin_beats_boss_when_dragapult_energy_is_incomplete():
    policy = DragapultWorldlinePolicy()
    options = [
        {"type": T_PLAY, "cardId": BOSS},
        {"type": T_PLAY, "cardId": CRISPIN},
    ]
    ctx = context(select={"option": options})
    assert policy.choose_single(options, ctx) == 1
    assert policy.last_runner_id == "CRISPIN_ENERGY_COMPLETION"


def test_planless_switch_and_retreat_are_not_promoted():
    policy = DragapultWorldlinePolicy()
    options = [
        {"type": T_PLAY, "cardId": SWITCH},
        {"type": T_RETREAT, "cardId": 666},
        {"type": T_PLAY, "cardId": CRISPIN},
    ]
    ctx = context(select={"option": options}, dragapult_ready=False)
    assert policy.choose_single(options, ctx) == 2
