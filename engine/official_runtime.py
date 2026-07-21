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


def _is_impossible_select(select: dict) -> bool:
    """The one known-crashing wire state: a mandatory (minCount=1) MAIN
    select (type=0) in TO_HAND context (7) with zero legal options. Neither
    [] nor any other observed submission has been shown safe for this state
    -- see artifacts/runtime_contract/impossible_select/ for the forensic
    bundle captured the first time this actually recurs live.
    """
    return (
        select.get("type") == 0
        and select.get("context") == 7
        and select.get("minCount") == 1
        and select.get("maxCount") == 1
        and len(select.get("option") or []) == 0
    )


def _capture_id(observation: dict, game_index: int | None, step: int) -> str:
    """timestamp + pid + game_index + step + raw_observation_sha256 --
    unique per occurrence so concurrent/parallel runs (or a second
    occurrence later in the same run) can never collide or overwrite a
    prior capture. The hash covers the *raw* observation bytes so an
    identical id also implies byte-identical evidence, not just a name
    collision.
    """
    import hashlib
    digest = hashlib.sha256(json.dumps(observation, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    return f"{int(time.time() * 1000)}_{os.getpid()}_{game_index if game_index is not None else 'na'}_{step}_{digest}"


def _capture_impossible_select_evidence(
    observation: dict,
    action: list[int],
    prev_observation: dict | None,
    prev_action: list[int] | None,
    *,
    output_dir: Path | None = None,
    game_index: int | None = None,
    step: int | None = None,
) -> None:
    """Fired automatically every time _is_impossible_select() matches --
    NOT once-per-process. Each occurrence gets its own immutable
    captures/<capture_id>/ directory (see _capture_id) so a rare second
    occurrence is never lost or silently overwritten; only a small
    capture_manifest.json at the stable base path is ever rewritten, and it
    only ever appends new entries or updates "latest", never removes
    history.

    Writes the full raw/converted/diff bundle the runtime contract audit
    requires, per occurrence. Does NOT call battle_select itself -- the
    caller (run_battle's main loop) makes the one real call and records the
    outcome (success or full traceback) via its own try/except, so this
    function only captures *pre*-call state (plus the action about to be
    submitted, saved verbatim as current_action.json).
    """
    import dataclasses

    base = output_dir or (Path(__file__).resolve().parents[1] / "artifacts" / "runtime_contract" / "impossible_select")
    base.mkdir(parents=True, exist_ok=True)
    capture_id = _capture_id(observation, game_index, step or 0)
    out = base / "captures" / capture_id
    out.mkdir(parents=True, exist_ok=True)
    select = observation.get("select") or {}

    (out / "raw_observation.json").write_text(json.dumps(observation, indent=2, ensure_ascii=False, default=str))
    (out / "raw_select.json").write_text(json.dumps(select, indent=2, ensure_ascii=False, default=str))
    # Full previous observation (not just its select) -- required to
    # reconstruct the parent state's hand/deck/discard/board, not just what
    # was being selected a moment before.
    (out / "previous_observation.json").write_text(
        json.dumps(prev_observation, indent=2, ensure_ascii=False, default=str)
    )
    (out / "previous_action.json").write_text(json.dumps(prev_action, indent=2, ensure_ascii=False, default=str))
    # The actual action this decision resolved to, saved standalone so the
    # evidence bundle is self-contained without needing the trace file too.
    (out / "current_action.json").write_text(json.dumps(action, indent=2, ensure_ascii=False, default=str))
    (out / "effect_context.json").write_text(json.dumps({
        "effect": select.get("effect"),
        "contextCard": select.get("contextCard"),
        "deck": select.get("deck"),
    }, indent=2, ensure_ascii=False, default=str))

    try:
        from black_engine.official_observation import normalize_official_observation
        from black_engine.truth import build_truth_state
        truth = build_truth_state(normalize_official_observation(observation))
        our_converted = {
            "select_type": truth.select_type, "select_context": truth.select_context,
            "min_count": truth.min_count, "max_count": truth.max_count,
            "option_count": len(truth.options), "actor": truth.actor,
        }
    except Exception as e:
        our_converted = {"conversion_error": repr(e)}

    try:
        import cg.api as capi
        official_dc = capi.to_observation_class(observation)
        official_select = dataclasses.asdict(official_dc).get("select") if dataclasses.is_dataclass(official_dc) else None
    except Exception as e:
        official_select = {"conversion_error": repr(e)}

    (out / "converted_select.json").write_text(json.dumps({
        "our_truth_state": our_converted, "official_select": official_select,
    }, indent=2, ensure_ascii=False, default=str))

    (out / "conversion_diff.json").write_text(json.dumps({
        "raw.type": select.get("type"), "converted.type": our_converted.get("select_type"),
        "official.type": (official_select or {}).get("type") if isinstance(official_select, dict) else None,
        "raw.context": select.get("context"), "converted.context": our_converted.get("select_context"),
        "official.context": (official_select or {}).get("context") if isinstance(official_select, dict) else None,
        "raw.option_count": len(select.get("option") or []), "converted.option_count": our_converted.get("option_count"),
        "official.option_count": len((official_select or {}).get("option") or []) if isinstance(official_select, dict) else None,
        "raw.effect": select.get("effect"),
        "official.effect": (official_select or {}).get("effect") if isinstance(official_select, dict) else None,
        "raw.contextCard": select.get("contextCard"),
        "official.contextCard": (official_select or {}).get("contextCard") if isinstance(official_select, dict) else None,
        "raw.deck": select.get("deck"),
        "official.deck": (official_select or {}).get("deck") if isinstance(official_select, dict) else None,
    }, indent=2, ensure_ascii=False, default=str))

    manifest_path = base / "capture_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {"captures": []}
    except Exception:
        manifest = {"captures": []}
    manifest.setdefault("captures", []).append({
        "capture_id": capture_id, "game_index": game_index, "step": step, "pid": os.getpid(),
        "captured_at_epoch_ms": int(time.time() * 1000),
    })
    manifest["latest"] = capture_id
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    return out


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
    game_index: int | None = None,
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
    prev_observation: dict | None = None
    prev_action: list[int] | None = None
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
            if _is_impossible_select(select):
                capture_dir = _capture_impossible_select_evidence(
                    observation, action, prev_observation, prev_action,
                    game_index=game_index, step=steps,
                )
                try:
                    next_observation = game.battle_select(action)
                    (capture_dir / "traceback.txt").write_text(f"battle_select({action!r}) SUCCEEDED -- no exception")
                except Exception:
                    import traceback as _tb2
                    (capture_dir / "traceback.txt").write_text(_tb2.format_exc())
                    raise
            else:
                next_observation = game.battle_select(action)
            prev_observation, prev_action = observation, action
            observation = next_observation
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
