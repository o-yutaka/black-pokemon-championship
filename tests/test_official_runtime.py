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
    from engine.official_runtime import _capture_impossible_select_evidence

    observation = {
        "current": {"yourIndex": 1, "turn": 20, "result": -1, "players": [{}, {
            "active": [], "bench": [], "hand": None, "handCount": 0,
            "discard": [], "prize": [None] * 6, "deckCount": 30,
        }]},
        "select": {"type": 0, "context": 7, "minCount": 1, "maxCount": 1, "option": [],
                   "effect": None, "contextCard": None, "deck": None},
        "logs": [],
    }
    prev_observation = {"current": {"yourIndex": 1, "turn": 19, "result": -1}, "select": {"type": 1, "context": 4}}
    prev_action = [0]
    current_action: list[int] = []

    capture_dir = _capture_impossible_select_evidence(
        observation, current_action, prev_observation, prev_action,
        output_dir=tmp_path, game_index=7, step=42,
    )

    # Evidence lives under a unique captures/<capture_id>/ directory -- the
    # base output_dir itself must stay untouched except for the manifest, so
    # a rare second occurrence can never overwrite a prior one.
    assert capture_dir.parent.parent == tmp_path
    assert capture_dir.parent.name == "captures"
    for name in (
        "raw_observation.json", "raw_select.json", "previous_observation.json",
        "previous_action.json", "current_action.json", "effect_context.json",
        "converted_select.json", "conversion_diff.json",
    ):
        assert (capture_dir / name).is_file(), f"missing {name}"

    assert json.loads((capture_dir / "previous_observation.json").read_text()) == prev_observation
    assert json.loads((capture_dir / "previous_action.json").read_text()) == prev_action
    assert json.loads((capture_dir / "current_action.json").read_text()) == current_action

    diff = json.loads((capture_dir / "conversion_diff.json").read_text())
    assert diff["raw.type"] == 0
    assert diff["raw.context"] == 7
    assert diff["raw.option_count"] == 0

    manifest = json.loads((tmp_path / "capture_manifest.json").read_text())
    assert manifest["latest"] == capture_dir.name
    assert manifest["captures"][-1]["game_index"] == 7
    assert manifest["captures"][-1]["step"] == 42

    # A second occurrence must get its own directory and must not remove or
    # overwrite the first capture's evidence or manifest history.
    second_capture_dir = _capture_impossible_select_evidence(
        observation, current_action, prev_observation, prev_action,
        output_dir=tmp_path, game_index=8, step=1,
    )
    assert second_capture_dir != capture_dir
    assert capture_dir.is_dir()
    assert (capture_dir / "raw_observation.json").is_file()
    manifest = json.loads((tmp_path / "capture_manifest.json").read_text())
    assert len(manifest["captures"]) == 2
    assert manifest["latest"] == second_capture_dir.name
