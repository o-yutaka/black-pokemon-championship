from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.evaluation.bundles import tree_sha256

REQUIRED_CG = ("__init__.py", "api.py", "game.py", "libcg.so", "sim.py", "utils.py")
MAIN = '''from __future__ import annotations
import os
import sys
from pathlib import Path


def _root() -> Path:
    candidates = [Path(os.environ.get("BLACK_BUNDLE_ROOT", ".")), Path.cwd()]
    module_file = globals().get("__file__")
    if isinstance(module_file, str):
        candidates.insert(0, Path(module_file).resolve().parent)
    for candidate in candidates:
        candidate = candidate.resolve()
        if all((candidate / name).is_file() for name in ("main.py", "deck.csv", "profile.json", "red_agent.py")):
            return candidate
    raise RuntimeError("red team bundle root not found")

ROOT = _root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from submission_contract import validate_runtime_layout
validate_runtime_layout(ROOT)
from red_agent import load_policy
POLICY = load_policy(ROOT)


def agent(obs, configuration=None):
    return POLICY.agent(obs, configuration)
'''
CONTRACT = '''from __future__ import annotations
from pathlib import Path

REQUIRED = ("main.py", "deck.csv", "profile.json", "red_agent.py", "submission_contract.py")
CG = ("__init__.py", "api.py", "game.py", "libcg.so", "sim.py", "utils.py")


def validate_runtime_layout(root):
    root = Path(root).resolve()
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    missing.extend(f"cg/{name}" for name in CG if not (root / "cg" / name).is_file())
    if missing:
        raise RuntimeError(f"red team bundle missing: {missing}")
    deck = [line.strip() for line in (root / "deck.csv").read_text().splitlines() if line.strip()]
    if len(deck) != 60 or any(not value.isdigit() for value in deck):
        raise RuntimeError("red team deck must be exactly 60 integer IDs")
    if (root / "cg" / "libcg.so").stat().st_size <= 0:
        raise RuntimeError("official cg/libcg.so is empty")
    return {"runtime": "PASS", "deck": 60}
'''


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evidence_identity(source: dict) -> str:
    source_type = source.get("source_type")
    if source_type == "official_replay":
        return "REPLAY_GROUNDED_RECONSTRUCTION"
    if source_type == "official_replay_and_frozen_black_candidate":
        return "REPLAY_AND_FROZEN_BLACK_RECONSTRUCTION"
    if source_type == "frozen_black_candidate":
        return "FROZEN_BLACK_CANDIDATE_RECONSTRUCTION"
    raise ValueError(f"unknown Red Team source_type={source_type!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and lock fixed Red Team Bundles against one exact candidate and official engine.")
    parser.add_argument("--cg-dir", required=True, type=Path)
    parser.add_argument("--candidate-bundle", required=True, type=Path)
    parser.add_argument("--out-dir", default=ROOT / "red_team" / "bundles", type=Path)
    parser.add_argument("--lock-out", default=ROOT / "artifacts" / "red_team_manifest.lock.json", type=Path)
    args = parser.parse_args()

    cg_dir = args.cg_dir.resolve()
    candidate = args.candidate_bundle.resolve()
    profiles = json.loads((ROOT / "red_team" / "profiles.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "red_team" / "replay_sources.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "red_team" / "manifest.json").read_text(encoding="utf-8"))
    if set(profiles) != set(sources) or set(profiles) != set(manifest["matchups"]):
        raise RuntimeError("profiles, sources, and manifest matchup sets must match exactly")
    for name in REQUIRED_CG:
        if not (cg_dir / name).is_file():
            raise FileNotFoundError(cg_dir / name)
    for name in ("main.py", "deck.csv", "submission_contract.py"):
        if not (candidate / name).is_file():
            raise FileNotFoundError(candidate / name)

    engine_sha = file_sha256(cg_dir / "libcg.so")
    candidate_engine = candidate / "cg" / "libcg.so"
    if not candidate_engine.is_file():
        raise FileNotFoundError(candidate_engine)
    candidate_engine_sha = file_sha256(candidate_engine)
    if candidate_engine_sha != engine_sha:
        raise RuntimeError(
            f"candidate/runner engine mismatch candidate={candidate_engine_sha} runner={engine_sha}"
        )
    candidate_sha = tree_sha256(candidate)
    manifest["promotion"]["candidate_bundle_sha256"] = candidate_sha
    manifest["promotion"]["engine_sha256"] = engine_sha

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for slug, profile in profiles.items():
        bundle = args.out_dir / slug
        if bundle.exists():
            shutil.rmtree(bundle)
        (bundle / "cg").mkdir(parents=True)
        shutil.copy2(ROOT / "red_team" / "decks" / f"{slug}.csv", bundle / "deck.csv")
        shutil.copy2(ROOT / "red_team" / "replay_grounded_agent.py", bundle / "red_agent.py")
        (bundle / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        (bundle / "main.py").write_text(MAIN, encoding="utf-8")
        (bundle / "submission_contract.py").write_text(CONTRACT, encoding="utf-8")
        for name in REQUIRED_CG:
            shutil.copy2(cg_dir / name, bundle / "cg" / name)
        digest = tree_sha256(bundle)
        try:
            bundle_path = str(bundle.relative_to(ROOT))
        except ValueError:
            bundle_path = str(bundle)
        manifest["matchups"][slug]["bundle_path"] = bundle_path
        manifest["matchups"][slug]["bundle_sha256"] = digest
        manifest["matchups"][slug]["evidence_identity"] = evidence_identity(sources[slug])
        manifest["matchups"][slug]["source"] = sources[slug]
        print(f"{slug} {digest}")

    args.lock_out.parent.mkdir(parents=True, exist_ok=True)
    args.lock_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidate_sha256": candidate_sha, "engine_sha256": engine_sha, "lock": str(args.lock_out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
