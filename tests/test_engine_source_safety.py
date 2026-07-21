from black_engine.engine_source_safety import (
    align_visualizer_selected,
    require_competition_use_notice,
    team_rocket_energy_attach_is_safe,
)


def test_visualizer_selected_shift_is_repaired_without_mutation():
    source = [
        {"state": "s0", "selected": None},
        {"state": "s1", "selected": [3]},
        {"state": "terminal", "selected": [8]},
    ]
    repaired = align_visualizer_selected(source)
    assert source[0]["selected"] is None
    assert repaired[0]["selected"] == [3]
    assert repaired[1]["selected"] == [8]
    assert repaired[2]["selected"] is None


def test_team_rocket_energy_rejects_non_rocket_target():
    option = {"card": "energy", "target": "pokemon"}
    resolve_card = lambda _o: {"onlyTeamRocket": True}
    resolve_target = lambda _o: {"teamRocket": False}
    assert not team_rocket_energy_attach_is_safe(
        option, resolve_card=resolve_card, resolve_target=resolve_target
    )


def test_team_rocket_energy_accepts_rocket_target():
    option = {"card": "energy", "target": "pokemon"}
    assert team_rocket_energy_attach_is_safe(
        option,
        resolve_card=lambda _o: {"onlyTeamRocket": True},
        resolve_target=lambda _o: {"teamRocket": True},
    )


def test_competition_notice_gate():
    require_competition_use_notice(
        "Competition use for local development, testing, validation, and benchmarking."
    )
