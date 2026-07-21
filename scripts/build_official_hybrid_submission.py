from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = {"mewtwo_spidops", "garchomp_spiritomb"}

MAIN_TEMPLATE = '''from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.factory import build_hybrid_policy
from black_engine.submission_runtime import OfficialHybridRuntime
from black_lab import build_policy, read_deck

CANDIDATE = {candidate!r}
DECK = read_deck(ROOT / "deck.csv")
BASE_POLICY = build_policy(CANDIDATE)
HYBRID_POLICY = build_hybrid_policy(CANDIDATE, BASE_POLICY, root=ROOT)
RUNTIME = OfficialHybridRuntime(
    HYBRID_POLICY,
    BASE_POLICY,
    DECK,
    budget_ms=float(os.environ.get("BLACK_AGENT_BUDGET_MS", "500")),
)


def agent(obs, configuration=None):
    return RUNTIME.agent(obs, configuration)
'''


def copy_required_tree(source_root: Path, output: Path, candidate: str) -> None:
    candidate_root = source_root / "candidates" / candidate
    required = [
        source_root / "black_engine",
        source_root / "black_lab.py",
        candidate_root / "deck.csv",
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    shutil.copytree(source_root / "black_engine", output / "black_engine", dirs_exist_ok=True)
    shutil.copy2(source_root / "black_lab.py", output / "black_lab.py")
    shutil.copy2(candidate_root / "deck.csv", output / "deck.csv")
    for directory in ("models",):
        src = source_root / directory
        if src.exists():
            shutil.copytree(src, output / directory, dirs_exist_ok=True)
    (output / "main.py").write_text(MAIN_TEMPLATE.format(candidate=candidate), encoding="utf-8")


def validate_official_cg(cg_dir: Path) -> None:
    required = {"__init__.py", "api.py", "game.py", "sim.py", "utils.py", "libcg.so"}
    missing = sorted(name for name in required if not (cg_dir / name).is_file())
    if missing:
        raise FileNotFoundError(f"official cg directory missing: {missing}")


def build(candidate: str, cg_dir: Path, out_zip: Path) -> Path:
    if candidate not in CANDIDATES:
        raise ValueError(f"unknown candidate: {candidate}")
    validate_official_cg(cg_dir)
    work = out_zip.parent / f".{out_zip.stem}.build"
    if work.exists():
        shutil.rmtree(work)
    submission = work / "submission"
    submission.mkdir(parents=True)
    copy_required_tree(ROOT, submission, candidate)
    shutil.copytree(cg_dir, submission / "cg")

    deck_lines = [line.strip() for line in (submission / "deck.csv").read_text().splitlines() if line.strip()]
    if len(deck_lines) != 60:
        raise ValueError(f"deck.csv must contain exactly 60 lines, got {len(deck_lines)}")

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(submission.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(work))
    shutil.rmtree(work)
    return out_zip


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=sorted(CANDIDATES), required=True)
    parser.add_argument("--cg-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    path = build(args.candidate, args.cg_dir.resolve(), args.out.resolve())
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
