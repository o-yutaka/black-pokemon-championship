import json
from types import SimpleNamespace

from engine.official_runtime import run_battle


class FakeGame:
    def __init__(self):
        self.finished = False
        self.actions = []

    def battle_start(self, deck0, deck1):
        assert len(deck0) == len(deck1) == 60
        return {
            "current": {"yourIndex": 0, "result": -1},
            "select": {"type": 9, "context": 41, "minCount": 1, "maxCount": 1, "option": [{}, {}]},
        }, SimpleNamespace(result=0)

    def battle_select(self, action):
        self.actions.append(action)
        return {"current": {"yourIndex": 0, "result": 0}, "select": None}

    def battle_finish(self):
        self.finished = True


def test_official_runner_normalizes_and_finishes():
    game = FakeGame()
    deck = list(range(60))

    def agent(obs, configuration=None):
        return 0

    report = run_battle(deck, agent, deck, agent, game_module=game)
    assert report["completed"] is True
    assert report["result"] == 0
    assert report["steps"] == 1
    assert report["error"] is None
    assert report["decision_ms_total"] >= 0
    assert report["decision_ms_max"] >= 0
    assert game.actions == [[0]]
    assert game.finished is True


def test_official_runner_exposes_read_only_decision_evidence():
    game = FakeGame()
    deck = list(range(60))
    observed = []

    def agent(obs, configuration=None):
        return 0

    def observer(obs, actor, raw_action, action, decision_ms):
        observed.append(
            {
                "actor": actor,
                "raw_action": raw_action,
                "action": action,
                "decision_ms": decision_ms,
                "context": obs["select"]["context"],
            }
        )

    report = run_battle(
        deck,
        agent,
        deck,
        agent,
        game_module=game,
        decision_observer=observer,
    )

    assert report["completed"] is True
    assert observed == [
        {
            "actor": 0,
            "raw_action": 0,
            "action": [0],
            "decision_ms": observed[0]["decision_ms"],
            "context": 41,
        }
    ]
    assert observed[0]["decision_ms"] >= 0
    assert game.actions == [[0]]


def test_official_runner_rejects_non_60_deck():
    game = FakeGame()
    try:
        run_battle([1], lambda *_: [0], [2] * 60, lambda *_: [0], game_module=game)
    except ValueError as exc:
        assert "60" in str(exc)
    else:
        raise AssertionError("non-60 deck was accepted")


def test_is_impossible_select_matches_exact_captured_signature():
    from engine.official_runtime import _is_impossible_select

    impossible = {"type": 0, "context": 7, "minCount": 1, "maxCount": 1, "option": []}
    assert _is_impossible_select(impossible) is True

    # Any one field differing must not match -- this predicate must stay
    # narrowly scoped to the one signature actually observed crashing.
    assert _is_impossible_select({**impossible, "type": 1}) is False
    assert _is_impossible_select({**impossible, "context": 8}) is False
    assert _is_impossible_select({**impossible, "minCount": 0}) is False
    assert _is_impossible_select({**impossible, "maxCount": 2}) is False
    assert _is_impossible_select({**impossible, "option": [{}]}) is False


def test_capture_impossible_select_evidence_writes_full_bundle(tmp_path):
    import engine.official_runtime as runtime_module
    from engine.official_runtime import _capture_impossible_select_evidence

    # Reset the module-level once-only guard so this test is independent of
    # test execution order / prior captures within the same process.
    runtime_module._IMPOSSIBLE_SELECT_CAPTURED = False

    observation = {
        "current": {"yourIndex": 1, "turn": 20, "result": -1, "players": [{}, {
            "active": [], "bench": [], "hand": None, "handCount": 0,
            "discard": [], "prize": [None] * 6, "deckCount": 30,
        }]},
        "select": {"type": 0, "context": 7, "minCount": 1, "maxCount": 1, "option": [],
                   "effect": None, "contextCard": None, "deck": None},
        "logs": [],
    }
    prev_observation = {"current": {"yourIndex": 1, "turn": 20}, "select": {"type": 1, "context": 4}}

    _capture_impossible_select_evidence(
        observation, [], prev_observation, [0], output_dir=tmp_path
    )

    for name in (
        "raw_observation.json", "raw_select.json", "previous_action.json",
        "effect_context.json", "converted_select.json", "conversion_diff.json",
    ):
        assert (tmp_path / name).is_file(), f"missing {name}"

    diff = json.loads((tmp_path / "conversion_diff.json").read_text())
    assert diff["raw.type"] == 0
    assert diff["raw.context"] == 7
    assert diff["raw.option_count"] == 0

    # The once-only guard must prevent a second call in the same process
    # from silently overwriting first-occurrence evidence.
    (tmp_path / "raw_select.json").write_text("SENTINEL")
    _capture_impossible_select_evidence(observation, [], prev_observation, [0], output_dir=tmp_path)
    assert (tmp_path / "raw_select.json").read_text() == "SENTINEL"
    runtime_module._IMPOSSIBLE_SELECT_CAPTURED = False
