from __future__ import annotations

from pathlib import Path
from typing import Any

from black_engine.support import read_deck, validate_deck

CANDIDATE = "dragapult_cinderace"
ACE_SPEC_IDS = {1088}
REQUIRED_SOURCE_FILES = ("main.py", "deck.csv", "submission_contract.py")
REQUIRED_SOURCE_DIRS = ("black_engine",)
REQUIRED_CG_FILES = ("__init__.py", "api.py", "game.py", "sim.py", "utils.py", "libcg.so")


class SubmissionContractError(RuntimeError):
    pass


def resolve_root(module_file: Any = None) -> Path:
    return Path(module_file).resolve().parent if isinstance(module_file, str) and module_file else Path.cwd().resolve()


def validate_source_layout(root: str | Path) -> dict:
    root = Path(root).resolve()
    missing = [name for name in REQUIRED_SOURCE_FILES if not (root / name).is_file()]
    missing.extend(name for name in REQUIRED_SOURCE_DIRS if not (root / name).is_dir())
    if missing:
        raise SubmissionContractError(f"source layout missing: {sorted(missing)}")
    report = validate_deck(read_deck(root / "deck.csv"), ACE_SPEC_IDS)
    if not report["ok"]:
        raise SubmissionContractError(str(report["violations"]))
    main_text = (root / "main.py").read_text(encoding="utf-8")
    forbidden = [token for token in ("candidates/", "build_hybrid", "candidate router") if token.lower() in main_text.lower()]
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
    return {**source, "runtime": "PASS", "libcg_size": (cg / "libcg.so").stat().st_size}


def require_runtime_layout(module_file: Any = None) -> Path:
    root = resolve_root(module_file)
    validate_runtime_layout(root)
    return root
