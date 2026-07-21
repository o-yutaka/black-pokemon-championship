from collections import Counter

from black_engine.dragapult_worldline_v2 import (
    ARTICUNO,
    ROCKET_MEWTWO_EX,
    SPIDOPS,
    DragapultWorldlinePolicy,
)
from black_engine.policy import CINDERACE, CRISPIN, DRAGAPULT_EX, SWITCH, T_PLAY, T_RETREAT


def pokemon(cid, serial, hp, max_hp, energies=()):
    return {
        "id": cid,
        "serial": serial,
        "hp": hp,
        "maxHp": max_hp,
        "energyCards": [{"id": energy} for energy in energies],
    }


def context(**overrides):
    value = {
        "me": 0,
        "opp": 1,
        "current": {"players": [{}, {}]},
        "select": {"option": []},
        "effect": -1,
        "context": -1,
        "active_id": CINDERACE,
        "opp_hp": 300,
        "opp_damage": 0,
        "opp_bench": 3,
        "bench_slots": 2,
        "deck_count": 20,
        "hand_ids": (),
        "discard_ids": (),
        "counts": Counter(),
        "mine": [],
        "theirs": [],
        "dragapult_lines": [],
        "dragapult_ready": False,
        "ready_count": 0,
        "azelf_ready": False,
        "our_prizes": 4,
        "opponent_prizes": 4,
        "rocket_mewtwo_matchup": True,
        "opponent_rocket_count": 5,
        "opponent_articuno_online": False,
        "ready_bench_dragapult_count": 0,
    }
    value.update(overrides)
    return value


def test_planless_retreat_is_a_rejected_worldline():
    policy = DragapultWorldlinePolicy()
    options = [
        {"type": T_RETREAT, "cardId": CINDERACE},
        {"type": T_PLAY, "cardId": CRISPIN},
    ]
    ctx = context(select={"option": options})
    retreat = policy._plan_for_option(0, options[0], ctx)
    assert retreat.illegal
    assert retreat.plan.plan_id == "NO_MANUAL_SWITCH_WITHOUT_ATTACK"
    assert policy.choose_single(options, ctx) == 1


def test_handoff_requires_ready_bench_dragapult_and_prize_pressure():
    policy = DragapultWorldlinePolicy()
    option = {"type": T_PLAY, "cardId": SWITCH}
    ctx = context(
        opp_hp=180,
        dragapult_ready=True,
        ready_count=1,
        ready_bench_dragapult_count=1,
        dragapult_lines=[pokemon(DRAGAPULT_EX, 10, 320, 320, (2, 5))],
    )
    result = policy._plan_for_option(0, option, ctx)
    assert not result.illegal
    assert result.plan.plan_id == "CINDERACE_HANDOFF"


def test_bomb_finishes_spidops_instead_of_wasting_damage_on_mewtwo():
    policy = DragapultWorldlinePolicy()
    ctx = context(active_id=CINDERACE, dragapult_ready=False, opponent_rocket_count=5)
    spidops = pokemon(SPIDOPS, 20, 10, 130)
    mewtwo = pokemon(ROCKET_MEWTWO_EX, 21, 80, 280)
    assert policy._bomb_target(spidops, 50, ctx) > policy._bomb_target(mewtwo, 50, ctx)


def test_articuno_blocks_basic_spread_but_not_spidops():
    policy = DragapultWorldlinePolicy()
    policy._latest_context = {
        "rocket_mewtwo_matchup": True,
        "opponent_articuno_online": True,
        "opponent_rocket_count": 5,
    }
    spidops = pokemon(SPIDOPS, 20, 70, 130)
    mewtwo = pokemon(ROCKET_MEWTWO_EX, 21, 80, 280)
    assert policy._spread_target(spidops) > policy._spread_target(mewtwo)
    assert policy._spread_target(mewtwo) == -10000


def test_prize_value_uses_official_card_rule_not_hp():
    from black_engine.prize_truth import prize_value

    assert prize_value(951) == 2
    assert prize_value(264) == 1
    assert prize_value(652) == 3


def test_articuno_protected_basic_does_not_trigger_cinderace_handoff():
    policy = DragapultWorldlinePolicy()
    options = [
        {"type": T_PLAY, "cardId": SWITCH},
        {"type": T_PLAY, "cardId": CRISPIN},
    ]
    ctx = context(
        select={"option": options},
        opp_hp=300,
        dragapult_ready=True,
        ready_count=1,
        ready_bench_dragapult_count=1,
        ready_bench_dragapult_serials=(10,),
        opponent_articuno_online=True,
        theirs=[pokemon(ARTICUNO, 30, 120, 120), pokemon(400, 31, 50, 50)],
    )
    result = policy._plan_for_option(0, options[0], ctx)
    assert result.illegal
    assert policy.choose_single(options, ctx) == 1


def test_switch_handoff_persists_exact_target_then_phantom_attack():
    policy = DragapultWorldlinePolicy()
    root_options = [
        {"type": T_PLAY, "cardId": SWITCH},
        {"type": T_PLAY, "cardId": CRISPIN},
    ]
    current = {
        "turn": 5,
        "players": [
            {
                "active": [pokemon(CINDERACE, 1, 170, 170)],
                "bench": [pokemon(DRAGAPULT_EX, 10, 320, 320, (2, 5))],
            },
            {"active": [pokemon(999, 20, 180, 180)], "bench": []},
        ],
    }
    ctx = context(
        current=current,
        select={"option": root_options},
        active_id=CINDERACE,
        opp_hp=180,
        dragapult_ready=True,
        ready_count=1,
        ready_bench_dragapult_count=1,
        ready_bench_dragapult_serials=(10,),
        dragapult_lines=[pokemon(DRAGAPULT_EX, 10, 320, 320, (2, 5))],
        turn=5,
    )
    assert policy.choose_single(root_options, ctx) == 0
    pending = policy.pending.get()
    assert pending is not None
    assert pending.candidate.plan_id == "SWITCH_HANDOFF_PHANTOM"
    assert len(pending.candidate.steps) == 2

    target_options = [
        {"type": 4, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 0},
    ]
    target_ctx = dict(ctx)
    target_ctx["select"] = {"option": target_options}
    assert policy.choose_single(target_options, target_ctx) == 0

    attack_options = [
        {"type": 13, "attackId": 154, "playerIndex": 0, "inPlayArea": 4, "inPlayIndex": 0},
        {"type": 14},
    ]
    attack_current = {
        "turn": 5,
        "players": [
            {"active": [pokemon(DRAGAPULT_EX, 10, 320, 320, (2, 5))], "bench": []},
            {"active": [pokemon(999, 20, 180, 180)], "bench": []},
        ],
    }
    attack_ctx = dict(ctx)
    attack_ctx.update({"current": attack_current, "select": {"option": attack_options}, "active_id": DRAGAPULT_EX})
    assert policy.choose_single(attack_options, attack_ctx) == 0
    assert policy.pending.get() is None
