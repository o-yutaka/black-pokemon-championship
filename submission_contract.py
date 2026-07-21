from __future__ import annotations

from pathlib import Path
from typing import Any

from black_engine.support import read_deck, validate_deck

CANDIDATE = "dragapult_cinderace"
ACE_SPEC_IDS = {1088}

ROOT_FILE_ORDER = (
    "main.py",
    "deck.csv",
    "submission_contract.py",
)
BLACK_ENGINE_FILE_ORDER = (
    "__init__.py",
    "policy.py",
    "dragapult_worldline.py",
    "runtime.py",
    "support.py",
    "worldline/__init__.py",
    "worldline/model.py",
    "worldline/judge.py",
    "worldline/vision.py",
    "worldline/pending.py",
)
REQUIRED_CG_FILES = (
    "__init__.py",
    "api.py",
    "game.py",
    "libcg.so",
    "sim.py",
    "utils.py",
)
ARCHIVE_FILE_ORDER = (
    *ROOT_FILE_ORDER,
    *(f"black_engine/{name}" for name in BLACK_ENGINE_FILE_ORDER),
    *(f"cg/{name}" for name in REQUIRED_CG_FILES),
)


class SubmissionContractError(RuntimeError):
    pass


def _looks_like_bundle_root(path: Path) -> bool:
    return all((path / name).is_file() for name in ROOT_FILE_ORDER)


def resolve_root(module_file: Any = None) -> Path:
    candidates: list[Path] = []
    if isinstance(module_file, str) and module_file:
        candidates.append(Path(module_file).resolve().parent)
    candidates.extend((Path("/kaggle_simulations/agent"), Path.cwd().resolve()))

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if _looks_like_bundle_root(candidate):
            return candidate

    raise SubmissionContractError(
        "submission bundle root not found; checked: "
        + ", ".join(str(path) for path in seen)
    )


def validate_source_layout(root: str | Path) -> dict:
    root = Path(root).resolve()
    missing = [name for name in ROOT_FILE_ORDER if not (root / name).is_file()]
    missing.extend(
        f"black_engine/{name}"
        for name in BLACK_ENGINE_FILE_ORDER
        if not (root / "black_engine" / name).is_file()
    )
    if missing:
        raise SubmissionContractError(f"source layout missing: {sorted(missing)}")

    report = validate_deck(read_deck(root / "deck.csv"), ACE_SPEC_IDS)
    if not report["ok"]:
        raise SubmissionContractError(str(report["violations"]))

    main_text = (root / "main.py").read_text(encoding="utf-8")
    forbidden = [
        token
        for token in ("candidates/", "build_hybrid", "candidate router", "RocketMewtwo")
        if token.lower() in main_text.lower()
    ]
    if forbidden:
        raise SubmissionContractError(f"non-canonical main.py tokens: {forbidden}")

    return {"root": str(root), "candidate": CANDIDATE, "deck": report}


def validate_runtime_layout(root: str | Path) -> dict:
    root = Path(root).resolve()
    source = validate_source_layout(root)
    cg = root / "cg"
    missing = [name for name in REQUIRED_CG_FILES if not (cg / name).is_file()]
    if missing:
        raise SubmissionContractError(f"runtime cg missing: {sorted(missing)}")
    if (cg / "libcg.so").stat().st_size <= 0:
        raise SubmissionContractError("cg/libcg.so is empty")
    return {
        **source,
        "runtime": "PASS",
        "libcg_size": (cg / "libcg.so").stat().st_size,
    }


def validate_archive_layout(root: str | Path) -> dict:
    root = Path(root).resolve()
    runtime = validate_runtime_layout(root)
    actual = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    expected = set(ARCHIVE_FILE_ORDER)
    missing = sorted(expected.difference(actual))
    unexpected = sorted(set(actual).difference(expected))
    if missing or unexpected:
        raise SubmissionContractError(
            f"archive layout mismatch: missing={missing}, unexpected={unexpected}"
        )
    if (root / "submission").exists():
        raise SubmissionContractError("extra top-level submission/ directory is forbidden")
    return {**runtime, "archive": "PASS", "files": list(ARCHIVE_FILE_ORDER)}


def require_runtime_layout(module_file: Any = None) -> Path:
    root = resolve_root(module_file)
    validate_runtime_layout(root)
    return root
