from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from submission_contract import CANDIDATE, validate_runtime_layout, validate_source_layout

CANDIDATES = {CANDIDATE}


def validate_official_cg(cg_dir: Path) -> None:
    required = {"__init__.py", "api.py", "game.py", "sim.py", "utils.py", "libcg.so"}
    missing = sorted(name for name in required if not (cg_dir / name).is_file())
    if missing:
        raise FileNotFoundError(f"official cg directory missing: {missing}")
    if (cg_dir / "libcg.so").stat().st_size <= 0:
        raise ValueError("official cg/libcg.so is empty")


def copy_submission_source(source_root: Path, output: Path) -> None:
    validate_source_layout(source_root)
    required_files = (
        "main.py",
        "deck.csv",
        "black_lab.py",
        "submission_contract.py",
    )
    for name in required_files:
        shutil.copy2(source_root / name, output / name)
    shutil.copytree(source_root / "black_engine", output / "black_engine", dirs_exist_ok=True)
    models = source_root / "models"
    if models.is_dir():
        shutil.copytree(models, output / "models", dirs_exist_ok=True)


def stage_submission(cg_dir: Path, destination: Path) -> Path:
    cg_dir = cg_dir.resolve()
    destination = destination.resolve()
    validate_official_cg(cg_dir)
    validate_source_layout(ROOT)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    copy_submission_source(ROOT, destination)
    shutil.copytree(cg_dir, destination / "cg")
    validate_runtime_layout(destination)

    # The submission entrypoint and deck must be byte-identical to the files
    # developed and reviewed at repository root. No final-stage generation or
    # candidate-specific rewrite is permitted.
    for name in ("main.py", "deck.csv", "submission_contract.py"):
        if (ROOT / name).read_bytes() != (destination / name).read_bytes():
            raise RuntimeError(f"staged submission drifted from canonical source: {name}")
    return destination


def build(candidate: str, cg_dir: Path, out_zip: Path) -> Path:
    if candidate != CANDIDATE:
        raise ValueError(
            f"this branch is submission-locked to {CANDIDATE}; requested={candidate}"
        )
    work = out_zip.parent / f".{out_zip.stem}.build"
    submission = work / "submission"
    stage_submission(cg_dir, submission)

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(submission.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(work))
    shutil.rmtree(work)
    return out_zip


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the byte-identical submission-first Dragapult package."
    )
    parser.add_argument("--candidate", choices=sorted(CANDIDATES), default=CANDIDATE)
    parser.add_argument("--cg-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    path = build(args.candidate, args.cg_dir.resolve(), args.out.resolve())
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
