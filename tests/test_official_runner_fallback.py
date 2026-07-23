from pathlib import Path
from types import SimpleNamespace

from black_engine.evaluation.bundles import LoadedBundle
from black_engine.evaluation.official_runner import run_game
import black_engine.evaluation.official_runner as runner


def test_official_runner_counts_submission_runtime_fallback(monkeypatch, tmp_path: Path):
    class FakeGame:
        def battle_start(self, deck0, deck1):
            return {
                "current": {"yourIndex": 0, "result": -1},
                "select": {"option": [{"type": 14}], "minCount": 1, "maxCount": 1},
            }, None

        def battle_select(self, action):
            return {"current": {"yourIndex": 1, "result": 0}, "select": None}

        def battle_finish(self):
            return None

    monkeypatch.setattr(runner, "_load_game", lambda cg_dir: FakeGame())
    fallback = LoadedBundle(
        tmp_path,
        lambda obs, configuration=None: [0],
        [1] * 60,
        "candidate",
        lambda obs, configuration=None: SimpleNamespace(
            selection=[0], source="fallback", error="invalid_selection"
        ),
    )
    opponent = LoadedBundle(
        tmp_path,
        lambda obs, configuration=None: [0],
        [1] * 60,
        "opponent",
    )

    record = run_game(
        matchup="fallback_probe",
        cg_dir=tmp_path,
        seat_bundles=(fallback, opponent),
        candidate_seat=0,
    )

    assert record.runtime.completed == 1
    assert record.runtime.fallback == 1
