from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build(cg_dir: Path, out_zip: Path) -> Path:
    from submission_contract import REQUIRED_CG_FILES, validate_runtime_layout, validate_source_layout

    validate_source_layout(ROOT)
    missing = [name for name in REQUIRED_CG_FILES if not (cg_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"official cg missing: {missing}")
    work = out_zip.parent / f".{out_zip.stem}.build"
    submission = work / "submission"
    if work.exists():
        shutil.rmtree(work)
    submission.mkdir(parents=True)
    for name in ("main.py", "deck.csv", "submission_contract.py"):
        shutil.copy2(ROOT / name, submission / name)
    shutil.copytree(ROOT / "black_engine", submission / "black_engine")
    shutil.copytree(cg_dir, submission / "cg")
    validate_runtime_layout(submission)
    for name in ("main.py", "deck.csv", "submission_contract.py"):
        if (ROOT / name).read_bytes() != (submission / name).read_bytes():
            raise RuntimeError(f"submission drift: {name}")
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(submission.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(work))
    shutil.rmtree(work)
    return out_zip


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cg-dir", required=True, type=Path)
    parser.add_argument("--out", default=ROOT / "artifacts" / "submission.zip", type=Path)
    args = parser.parse_args()
    print(build(args.cg_dir.resolve(), args.out.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
