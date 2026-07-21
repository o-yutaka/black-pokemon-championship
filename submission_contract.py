from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

CANDIDATE = "dragapult_cinderace"
REQUIRED_SOURCE_FILES = (
    "main.py",
    "deck.csv",
    "black_lab.py",
    "submission_contract.py",
)
REQUIRED_SOURCE_DIRS = ("black_engine",)
REQUIRED_CG_FILES = (
    "__init__.py",
    "api.py",
    "game.py",
    "sim.py",
    "utils.py",
    "libcg.so",
)
FORBIDDEN_MAIN_TOKENS = (
    "parents[",
    "candidates/",
    "candidates\\",
    "/home/user/",
    "MAIN_TEMPLATE",
)


class SubmissionContractError(RuntimeError):
    pass


def resolve_runtime_root(module_file: Any = None) -> Path:
    if isinstance(module_file, str) and module_file:
        return Path(module_file).resolve().parent
    return Path.cwd().resolve()


def read_deck_ids(path: str | Path) -> list[int]:
    values: list[int] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if not row:
                continue
            value = str(row[0]).strip()
            if not value:
                continue
            if not value.isdigit():
                raise SubmissionContractError(f"deck.csv contains non-card value: {value!r}")
            values.append(int(value))
    return values


def validate_deck_file(path: str | Path) -> dict:
    deck = read_deck_ids(path)
    if len(deck) != 60:
        raise SubmissionContractError(f"deck.csv must contain exactly 60 card IDs, got {len(deck)}")
    return {"total": len(deck), "unique": len(set(deck)), "deck": deck}


def validate_source_layout(root: str | Path) -> dict:
    root = Path(root).resolve()
    missing = [name for name in REQUIRED_SOURCE_FILES if not (root / name).is_file()]
    missing.extend(name for name in REQUIRED_SOURCE_DIRS if not (root / name).is_dir())
    if missing:
        raise SubmissionContractError(f"submission source layout missing: {sorted(missing)}")

    main_text = (root / "main.py").read_text(encoding="utf-8")
    forbidden = [token for token in FORBIDDEN_MAIN_TOKENS if token in main_text]
    if forbidden:
        raise SubmissionContractError(
            "main.py is not submission-root-local; forbidden tokens=" + repr(forbidden)
        )
    if "def agent(" not in main_text:
        raise SubmissionContractError("main.py must expose def agent(obs, configuration=None)")
    deck_report = validate_deck_file(root / "deck.csv")
    return {
        "root": str(root),
        "candidate": CANDIDATE,
        "deck_total": deck_report["total"],
        "source_files": list(REQUIRED_SOURCE_FILES),
        "source_dirs": list(REQUIRED_SOURCE_DIRS),
    }


def validate_runtime_layout(root: str | Path) -> dict:
    root = Path(root).resolve()
    source = validate_source_layout(root)
    cg = root / "cg"
    if not cg.is_dir():
        raise SubmissionContractError("submission runtime layout missing cg/")
    missing = [name for name in REQUIRED_CG_FILES if not (cg / name).is_file()]
    if missing:
        raise SubmissionContractError(f"submission runtime cg/ missing: {sorted(missing)}")
    if (cg / "libcg.so").stat().st_size <= 0:
        raise SubmissionContractError("cg/libcg.so is empty")
    return {
        **source,
        "runtime": "PASS",
        "cg_files": list(REQUIRED_CG_FILES),
        "libcg_size": (cg / "libcg.so").stat().st_size,
    }


def require_runtime_layout(module_file: Any = None) -> Path:
    root = resolve_runtime_root(module_file)
    validate_runtime_layout(root)
    return root
