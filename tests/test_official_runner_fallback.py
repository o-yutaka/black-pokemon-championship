import time
from pathlib import Path
from types import SimpleNamespace

from black_engine.evaluation.bundles import LoadedBundle
from black_engine.evaluation.official_runner import run_game
import black_engine.evaluation.official_runner as runner


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


def opponent_bundle(tmp_path: Path) -> LoadedBundle:
    return LoadedBundle(tmp_path, lambda obs, configuration=None: [0], [1] * 60, "opponent")


def test_official_runner_counts_submission_runtime_fallback(monkeypatch, tmp_path: Path):
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
    record = run_game(
        matchup="fallback_probe",
        cg_dir=tmp_path,
        seat_bundles=(fallback, opponent_bundle(tmp_path)),
        candidate_seat=0,
    )
    assert record.runtime.completed == 1
    assert record.runtime.fallback == 1


def test_official_runner_interrupts_stuck_decision(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(runner, "_load_game", lambda cg_dir: FakeGame())

    def stuck(obs, configuration=None):
        time.sleep(0.2)
        return [0]

    candidate = LoadedBundle(tmp_path, stuck, [1] * 60, "candidate")
    started = time.perf_counter()
    record = run_game(
        matchup="timeout_probe",
        cg_dir=tmp_path,
        seat_bundles=(candidate, opponent_bundle(tmp_path)),
        candidate_seat=0,
        decision_timeout_ms=10.0,
    )
    elapsed = time.perf_counter() - started
    assert record.runtime.timeout == 1
    assert record.runtime.completed == 0
    assert elapsed < 0.15
