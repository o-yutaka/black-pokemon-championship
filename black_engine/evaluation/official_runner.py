from __future__ import annotations

import hashlib
import importlib
import json
import signal
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from .bundles import LoadedBundle, load_bundle
from .models import GameRecord, MatchupSummary, RuntimeCounters
from .statistics import percentile, wilson_interval


class DecisionTimeoutError(TimeoutError):
    pass


def legal_selection(obs: dict, action: Any) -> bool:
    select = obs.get("select") if isinstance(obs.get("select"), dict) else {}
    options = select.get("option") if isinstance(select.get("option"), list) else []
    minimum = max(0, int(select.get("minCount", 0) or 0))
    maximum_raw = select.get("maxCount", minimum)
    maximum = minimum if maximum_raw is None else max(0, int(maximum_raw))
    if not isinstance(action, list):
        return False
    if any(type(value) is not int for value in action):
        return False
    return minimum <= len(action) <= maximum and len(action) == len(set(action)) and all(0 <= value < len(options) for value in action)


def _result(obs: dict | None) -> int:
    if not isinstance(obs, dict):
        return -1
    current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
    value = current.get("result", -1)
    return value if type(value) is int else -1


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def _hard_timeout(timeout_ms: float) -> Iterator[None]:
    """Interrupt a stuck Python decision on Linux/WSL instead of measuring after return."""
    timeout_seconds = max(0.001, float(timeout_ms) / 1000.0)
    supported = (
        hasattr(signal, "SIGALRM")
        and hasattr(signal, "setitimer")
        and threading.current_thread() is threading.main_thread()
    )
    if not supported:
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def _raise_timeout(signum, frame):
        raise DecisionTimeoutError(f"decision exceeded {timeout_ms:.3f} ms")

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer != (0.0, 0.0):
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def _load_game(cg_dir: Path):
    resolved = cg_dir.resolve()
    parent = str(resolved.parent)
    sys.path[:] = [value for value in sys.path if value != parent]
    sys.path.insert(0, parent)
    sys.modules.pop("cg.game", None)
    sys.modules.pop("cg", None)
    module = importlib.import_module("cg.game")
    module_path = Path(module.__file__).resolve().parent
    if module_path != resolved:
        raise RuntimeError(f"wrong cg.game imported: expected={resolved} actual={module_path}")
    return module


def run_game(
    *,
    matchup: str,
    cg_dir: Path,
    seat_bundles: tuple[LoadedBundle, LoadedBundle],
    candidate_seat: int,
    max_steps: int = 20000,
    decision_timeout_ms: float = 1000.0,
) -> GameRecord:
    game = _load_game(cg_dir)
    runtime = RuntimeCounters()
    decision_ms: list[float] = []
    obs: dict | None = None
    error: str | None = None
    steps = 0
    try:
        obs, _ = game.battle_start(seat_bundles[0].deck, seat_bundles[1].deck)
        while _result(obs) not in (0, 1) and steps < max_steps:
            if not isinstance(obs, dict):
                runtime.runtime_error += 1
                error = "official engine returned non-dict observation"
                break
            current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
            actor = current.get("yourIndex", 0)
            if actor not in (0, 1):
                runtime.runtime_error += 1
                error = f"invalid yourIndex={actor!r}"
                break
            select = obs.get("select") if isinstance(obs.get("select"), dict) else {}
            options = select.get("option") if isinstance(select.get("option"), list) else []
            minimum = max(0, int(select.get("minCount", 0) or 0))
            if minimum > 0 and not options:
                runtime.mandatory_empty += 1
                error = "mandatory empty official selection"
                break
            started = time.perf_counter()
            try:
                bundle = seat_bundles[actor]
                with _hard_timeout(decision_timeout_ms):
                    if bundle.decide is not None:
                        decision = bundle.decide(obs, None)
                        action = decision.selection
                        decision_source = str(getattr(decision, "source", "unknown"))
                        if decision_source == "fallback":
                            runtime.fallback += 1
                            error = error or f"agent fallback seat={actor}: {getattr(decision, 'error', None)}"
                    else:
                        action = bundle.agent(obs, None)
            except DecisionTimeoutError as exc:
                runtime.timeout += 1
                error = f"decision timeout seat={actor}: {exc}"
                break
            except Exception as exc:
                runtime.crash += 1
                error = f"agent crash seat={actor}: {type(exc).__name__}: {exc}"
                break
            elapsed = (time.perf_counter() - started) * 1000.0
            decision_ms.append(elapsed)
            if elapsed > decision_timeout_ms:
                runtime.timeout += 1
                error = f"decision timeout seat={actor} elapsed_ms={elapsed:.3f}"
                break
            if not legal_selection(obs, action):
                runtime.illegal_action += 1
                error = f"illegal action seat={actor} action={action!r}"
                break
            obs = game.battle_select(action)
            steps += 1
        result = _result(obs)
        if result in (0, 1):
            runtime.completed += 1
            result_label = "DONE"
            winner = result
        elif steps >= max_steps:
            runtime.runtime_error += 1
            result_label = "STEP_LIMIT"
            winner = None
            error = error or f"step limit {max_steps}"
        else:
            result_label = "ERROR"
            winner = None
    except Exception as exc:
        runtime.crash += 1
        result_label = "CRASH"
        winner = None
        error = f"engine crash: {type(exc).__name__}: {exc}"
    finally:
        try:
            game.battle_finish()
        except Exception as exc:
            runtime.runtime_error += 1
            error = error or f"battle_finish: {type(exc).__name__}: {exc}"
    return GameRecord(
        matchup=matchup,
        candidate_bundle_sha256=seat_bundles[candidate_seat].sha256,
        opponent_bundle_sha256=seat_bundles[1 - candidate_seat].sha256,
        candidate_seat=candidate_seat,
        winner_seat=winner,
        result=result_label,
        steps=steps,
        decision_ms=decision_ms,
        runtime=runtime,
        error=error,
    )


def summarize(matchup: str, records: list[GameRecord], evidence_mode: str = "PROMOTION", engine_sha256: str = "") -> MatchupSummary:
    runtime = RuntimeCounters()
    timings: list[float] = []
    wins = losses = draws_or_errors = 0
    seat0_games = seat1_games = seat0_wins = seat1_wins = 0
    for record in records:
        runtime.merge(record.runtime)
        timings.extend(record.decision_ms)
        if record.candidate_seat == 0:
            seat0_games += 1
        else:
            seat1_games += 1
        if record.winner_seat is None:
            draws_or_errors += 1
        elif record.candidate_win:
            wins += 1
            if record.candidate_seat == 0:
                seat0_wins += 1
            else:
                seat1_wins += 1
        else:
            losses += 1
    candidate_hashes = {record.candidate_bundle_sha256 for record in records}
    opponent_hashes = {record.opponent_bundle_sha256 for record in records}
    if len(candidate_hashes) != 1 or len(opponent_hashes) != 1:
        raise ValueError("mixed bundle identities in one matchup summary")
    decided = wins + losses
    low, high = wilson_interval(wins, decided)
    return MatchupSummary(
        matchup=matchup,
        games=len(records),
        wins=wins,
        losses=losses,
        draws_or_errors=draws_or_errors,
        seat0_games=seat0_games,
        seat1_games=seat1_games,
        seat0_wins=seat0_wins,
        seat1_wins=seat1_wins,
        win_rate=wins / decided if decided else 0.0,
        wilson_low=low,
        wilson_high=high,
        runtime=runtime,
        mean_decision_ms=sum(timings) / len(timings) if timings else 0.0,
        p95_decision_ms=percentile(timings, 0.95),
        evidence_mode=evidence_mode,
        candidate_bundle_sha256=next(iter(candidate_hashes)),
        opponent_bundle_sha256=next(iter(opponent_hashes)),
        engine_sha256=engine_sha256,
    )


def run_matchup(
    *,
    matchup: str,
    cg_dir: str | Path,
    candidate_bundle: str | Path,
    opponent_bundle: str | Path,
    games: int,
    out_dir: str | Path,
    evidence_mode: str = "PROMOTION",
    max_steps: int = 20000,
    decision_timeout_ms: float = 1000.0,
) -> MatchupSummary:
    if games <= 0 or games % 2:
        raise ValueError("games must be a positive even number for seat balance")
    candidate_root = Path(candidate_bundle)
    opponent_root = Path(opponent_bundle)
    engine_path = Path(cg_dir).resolve() / "libcg.so"
    if not engine_path.is_file():
        raise FileNotFoundError(engine_path)
    engine_sha256 = _file_sha256(engine_path)
    for bundle_root in (candidate_root, opponent_root):
        bundled_engine = bundle_root.resolve() / "cg" / "libcg.so"
        if not bundled_engine.is_file():
            raise FileNotFoundError(bundled_engine)
        bundled_sha = _file_sha256(bundled_engine)
        if bundled_sha != engine_sha256:
            raise RuntimeError(
                f"bundle/runner engine mismatch bundle={bundle_root} "
                f"bundle_sha={bundled_sha} runner_sha={engine_sha256}"
            )
    records: list[GameRecord] = []
    for index in range(games):
        candidate = load_bundle(candidate_root)
        opponent = load_bundle(opponent_root)
        candidate_seat = index % 2
        seats = (candidate, opponent) if candidate_seat == 0 else (opponent, candidate)
        records.append(
            run_game(
                matchup=matchup,
                cg_dir=Path(cg_dir),
                seat_bundles=seats,
                candidate_seat=candidate_seat,
                max_steps=max_steps,
                decision_timeout_ms=decision_timeout_ms,
            )
        )
    summary = summarize(matchup, records, evidence_mode=evidence_mode, engine_sha256=engine_sha256)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "games.jsonl").write_text(
        "".join(json.dumps(record.to_dict(), ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    (out / "summary.json").write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
