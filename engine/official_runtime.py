from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from black_lab import normalize_selection


class EngineUnavailable(RuntimeError):
    """Raised when the local official cabt engine cannot be resolved safely."""


@dataclass(frozen=True)
class OfficialEngineProvenance:
    cg_dir: str
    library_path: str
    library_sha256: str
    library_size: int
    python_game_path: str
    server_runtime: str = "cabt 1.32.0 (competition authority; exact server binary hash unverified)"
    seed_control: str = "native battle_start exposes no seed parameter"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_cg_dirs(explicit: str | Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("CABT_CG_DIR"):
        candidates.append(Path(os.environ["CABT_CG_DIR"]))
    if os.environ.get("HROS_ROOT"):
        candidates.append(Path(os.environ["HROS_ROOT"]) / "submission" / "cg")
    candidates.extend(
        [
            Path("/home/user/HROS/submission/cg"),
            Path.cwd() / "submission" / "cg",
            Path.cwd() / "cg",
        ]
    )
    unique: list[Path] = []
    for value in candidates:
        resolved = value.expanduser().resolve()
        if resolved not in unique:
            unique.append(resolved)
    return unique


def locate_cg_dir(explicit: str | Path | None = None) -> Path:
    checked: list[str] = []
    for directory in _candidate_cg_dirs(explicit):
        checked.append(str(directory))
        if (
            directory.is_dir()
            and (directory / "game.py").is_file()
            and (directory / "sim.py").is_file()
            and (directory / "libcg.so").is_file()
        ):
            return directory
    raise EngineUnavailable(
        "Official cg directory not found. Checked: " + ", ".join(checked)
    )


def load_official_game(
    cg_dir: str | Path | None = None,
) -> tuple[ModuleType, OfficialEngineProvenance]:
    directory = locate_cg_dir(cg_dir)
    parent = str(directory.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    importlib.invalidate_caches()
    game = importlib.import_module("cg.game")
    for name in ("battle_start", "battle_select", "battle_finish"):
        if not callable(getattr(game, name, None)):
            raise EngineUnavailable(f"cg.game missing required callable: {name}")
    library = directory / "libcg.so"
    provenance = OfficialEngineProvenance(
        cg_dir=str(directory),
        library_path=str(library),
        library_sha256=_sha256(library),
        library_size=library.stat().st_size,
        python_game_path=str(Path(game.__file__).resolve()),
    )
    return game, provenance


def _battle_result(obs: dict | None) -> int:
    if not isinstance(obs, dict):
        return -1
    current = obs.get("current")
    if not isinstance(current, dict):
        return -1
    result = current.get("result", -1)
    return result if type(result) is int else -1


def _actor_index(obs: dict) -> int:
    current = obs.get("current")
    if not isinstance(current, dict):
        raise RuntimeError("observation.current is unavailable")
    actor = current.get("yourIndex")
    if actor not in (0, 1):
        raise RuntimeError(f"invalid observation.current.yourIndex={actor!r}")
    return int(actor)


def _legal_action(obs: dict, action: Any) -> list[int]:
    normalized = normalize_selection(obs, action)
    if normalized is None:
        normalized = []
    if not isinstance(normalized, list) or any(type(v) is not int for v in normalized):
        raise RuntimeError(f"agent returned invalid action shape: {normalized!r}")
    return normalized


def _start_observation(game: ModuleType, deck0: list[int], deck1: list[int]):
    started = game.battle_start(deck0, deck1)
    if not isinstance(started, tuple) or len(started) != 2:
        raise RuntimeError("battle_start must return (observation, StartData)")
    observation, start_data = started
    if observation is None:
        raise RuntimeError(f"battle_start failed: {start_data!r}")
    if not isinstance(observation, dict):
        raise RuntimeError(f"battle_start returned invalid observation: {type(observation)!r}")
    return observation, start_data


def run_battle(
    deck0: list[int],
    agent0: Callable[[dict, Any], Any],
    deck1: list[int],
    agent1: Callable[[dict, Any], Any],
    *,
    cg_dir: str | Path | None = None,
    max_steps: int = 20000,
    trace_path: str | Path | None = None,
    game_module: ModuleType | None = None,
    decision_observer: Callable[[dict, int, Any, list[int], float], None] | None = None,
) -> dict:
    """Run one sequential official-engine battle.

    The native engine is process-global, so this runner is intentionally sequential.
    It never claims deterministic seeding because battle_start(deck0, deck1) exposes
    no seed parameter in the official Python contract.

    ``decision_observer`` is an additive evidence hook.  It receives the unmodified
    public observation, acting seat, raw policy return, normalized legal action, and
    elapsed decision milliseconds before ``battle_select``.  The hook cannot alter
    the selected action or the official engine state.
    """
    if len(deck0) != 60 or len(deck1) != 60:
        raise ValueError("both decks must contain exactly 60 card IDs")
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")

    provenance = None
    game = game_module
    if game is None:
        game, provenance = load_official_game(cg_dir)

    traces: list[dict] = []
    observation: dict | None = None
    start_data: Any = None
    error: str | None = None
    steps = 0
    try:
        observation, start_data = _start_observation(game, list(deck0), list(deck1))
        while steps < max_steps:
            result = _battle_result(observation)
            if result in (0, 1):
                break
            actor = _actor_index(observation)
            selected_agent = agent0 if actor == 0 else agent1
            decision_started = time.perf_counter()
            raw_action = selected_agent(observation, None)
            decision_ms = (time.perf_counter() - decision_started) * 1000.0
            action = _legal_action(observation, raw_action)
            if decision_observer is not None:
                decision_observer(observation, actor, raw_action, action, decision_ms)
            select = observation.get("select") or {}
            traces.append(
                {
                    "step": steps,
                    "actor": actor,
                    "select_type": select.get("type"),
                    "select_context": select.get("context"),
                    "min_count": select.get("minCount"),
                    "max_count": select.get("maxCount"),
                    "option_count": len(select.get("option") or []),
                    "action": action,
                    "decision_ms": round(decision_ms, 6),
                }
            )
            observation = game.battle_select(action)
            if not isinstance(observation, dict):
                raise RuntimeError(
                    f"battle_select returned invalid observation: {type(observation)!r}"
                )
            steps += 1
        else:
            raise RuntimeError(f"max_steps exceeded: {max_steps}")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            game.battle_finish()
        except Exception as finish_exc:
            finish_error = f"{type(finish_exc).__name__}: {finish_exc}"
            error = f"{error}; battle_finish={finish_error}" if error else finish_error

    result = _battle_result(observation)
    decision_times = [float(row["decision_ms"]) for row in traces]
    report = {
        "result": result,
        "steps": steps,
        "completed": result in (0, 1) and error is None,
        "error": error,
        "start_data": repr(start_data),
        "provenance": asdict(provenance) if provenance else {"mode": "injected_test_double"},
        "trace_count": len(traces),
        "decision_ms_total": round(sum(decision_times), 6),
        "decision_ms_max": round(max(decision_times, default=0.0), 6),
    }
    if trace_path:
        destination = Path(trace_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            for row in traces:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return report
