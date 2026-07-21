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
    assert game.actions == [[0]]
    assert game.finished is True


def test_official_runner_rejects_non_60_deck():
    game = FakeGame()
    try:
        run_battle([1], lambda *_: [0], [2] * 60, lambda *_: [0], game_module=game)
    except ValueError as exc:
        assert "60" in str(exc)
    else:
        raise AssertionError("non-60 deck was accepted")
