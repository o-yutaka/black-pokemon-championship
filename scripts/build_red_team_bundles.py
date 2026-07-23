from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

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
    libcg = root / "cg" / "libcg.so"
    if libcg.stat().st_size <= 0 or not libcg.read_bytes().startswith(b"\\x7fELF"):
        raise RuntimeError("official cg/libcg.so must be a nonempty ELF shared object")
    return {"runtime": "PASS", "deck": 60}
'''


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_deck(path: Path) -> list[int]:
    rows = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(rows) != 60 or any(not value.isdigit() for value in rows):
        raise RuntimeError(f"deck must contain exactly 60 integer IDs: {path}")
    return [int(value) for value in rows]


def evidence_identity(source: dict) -> str:
    source_type = source.get("source_type")
    if source_type == "official_replay":
        return "REPLAY_GROUNDED_RECONSTRUCTION"
    if source_type == "official_replay_and_frozen_black_candidate":
        return "REPLAY_AND_FROZEN_BLACK_RECONSTRUCTION"
    if source_type == "frozen_black_candidate":
        return "FROZEN_BLACK_CANDIDATE_RECONSTRUCTION"
    raise ValueError(f"unknown Red Team source_type={source_type!r}")


def _safe_extract(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise RuntimeError(f"unsafe archive member: {member.name}")
        archive.extractall(destination, filter="data")


def _run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed cwd={cwd} command={command}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )


def _build_replay_bundle(*, slug: str, profile: dict, cg_dir: Path, bundle: Path) -> None:
    (bundle / "cg").mkdir(parents=True)
    shutil.copy2(ROOT / "red_team" / "decks" / f"{slug}.csv", bundle / "deck.csv")
    shutil.copy2(ROOT / "red_team" / "replay_grounded_agent.py", bundle / "red_agent.py")
    (bundle / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle / "main.py").write_text(MAIN, encoding="utf-8")
    (bundle / "submission_contract.py").write_text(CONTRACT, encoding="utf-8")
    for name in REQUIRED_CG:
        shutil.copy2(cg_dir / name, bundle / "cg" / name)


def _build_git_submission_bundle(*, slug: str, spec: dict, cg_dir: Path, bundle: Path) -> None:
    commit = str(spec.get("commit_sha", ""))
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit.lower()):
        raise RuntimeError(f"{slug}: invalid frozen commit SHA: {commit!r}")
    builder_rel = PurePosixPath(str(spec.get("builder_path", "scripts/build_submission.py")))
    if builder_rel.is_absolute() or ".." in builder_rel.parts:
        raise RuntimeError(f"{slug}: unsafe builder path: {builder_rel}")

    _run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix=f"black_red_{slug}_") as raw:
        temp = Path(raw)
        source_tar = temp / "source.tar"
        source_root = temp / "source"
        output_archive = temp / "submission.tar.gz"
        _run(["git", "archive", "--format=tar", "--output", str(source_tar), commit], cwd=ROOT)
        _safe_extract(source_tar, source_root)
        builder = source_root / builder_rel.as_posix()
        if not builder.is_file():
            raise RuntimeError(f"{slug}: frozen commit missing builder {builder_rel}")
        _run(
            [sys.executable, str(builder), "--cg-dir", str(cg_dir), "--out", str(output_archive)],
            cwd=source_root,
        )
        _safe_extract(output_archive, bundle)

    expected_deck = _read_deck(ROOT / "red_team" / "decks" / f"{slug}.csv")
    actual_deck = _read_deck(bundle / "deck.csv")
    if actual_deck != expected_deck:
        raise RuntimeError(f"{slug}: frozen executable deck differs from locked red_team deck")
    if not (bundle / "cg" / "libcg.so").read_bytes().startswith(b"\x7fELF"):
        raise RuntimeError(f"{slug}: frozen executable bundle did not contain an ELF libcg.so")


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
    promotion_sources = json.loads((ROOT / "red_team" / "promotion_sources.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "red_team" / "manifest.json").read_text(encoding="utf-8"))
    if set(profiles) != set(sources) or set(profiles) != set(manifest["matchups"]):
        raise RuntimeError("profiles, sources, and manifest matchup sets must match exactly")
    if not set(promotion_sources).issubset(set(profiles)):
        raise RuntimeError("promotion_sources contains an unknown matchup")
    for name in REQUIRED_CG:
        if not (cg_dir / name).is_file():
            raise FileNotFoundError(cg_dir / name)
    if not (cg_dir / "libcg.so").read_bytes().startswith(b"\x7fELF"):
        raise RuntimeError("official cg/libcg.so must be an ELF shared object")
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
        spec = promotion_sources.get(slug)
        strength = str(manifest["matchups"][slug].get("strength_evidence", ""))
        if spec is not None:
            if strength != "PROMOTION":
                raise RuntimeError(f"{slug}: frozen executable source requires strength_evidence=PROMOTION")
            _build_git_submission_bundle(slug=slug, spec=spec, cg_dir=cg_dir, bundle=bundle)
            identity = str(spec.get("evidence_identity", "FROZEN_BLACK_EXECUTABLE_BUNDLE"))
            build_mode = "GIT_SUBMISSION_COMMIT"
            manifest["matchups"][slug]["promotion_source"] = spec
        else:
            if strength != "STRESS_ONLY":
                raise RuntimeError(f"{slug}: replay reconstruction cannot be promotion evidence")
            _build_replay_bundle(slug=slug, profile=profile, cg_dir=cg_dir, bundle=bundle)
            identity = evidence_identity(sources[slug])
            build_mode = "REPLAY_GROUNDED_RECONSTRUCTION"

        bundled_engine_sha = file_sha256(bundle / "cg" / "libcg.so")
        if bundled_engine_sha != engine_sha:
            raise RuntimeError(f"{slug}: built bundle engine SHA mismatch")
        digest = tree_sha256(bundle)
        try:
            bundle_path = str(bundle.relative_to(ROOT))
        except ValueError:
            bundle_path = str(bundle)
        manifest["matchups"][slug]["bundle_path"] = bundle_path
        manifest["matchups"][slug]["bundle_sha256"] = digest
        manifest["matchups"][slug]["evidence_identity"] = identity
        manifest["matchups"][slug]["build_mode"] = build_mode
        manifest["matchups"][slug]["source"] = sources[slug]
        print(f"{slug} {strength} {digest}")

    args.lock_out.parent.mkdir(parents=True, exist_ok=True)
    args.lock_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidate_sha256": candidate_sha, "engine_sha256": engine_sha, "lock": str(args.lock_out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
