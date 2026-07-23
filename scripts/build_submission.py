from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from submission_contract import (
    ARCHIVE_FILE_ORDER,
    BLACK_ENGINE_FILE_ORDER,
    REQUIRED_CG_FILES,
    ROOT_FILE_ORDER,
    SubmissionContractError,
    validate_archive_layout,
    validate_source_layout,
)


def _is_tar_gz(path: Path) -> bool:
    return path.name.endswith(".tar.gz") or path.name.endswith(".tgz")


def _normalized_tarinfo(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.mode = 0o644
    return info


def inspect_archive(archive_path: Path, expected_root: Path | None = None) -> dict:
    archive_path = archive_path.resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    if not _is_tar_gz(archive_path):
        raise SubmissionContractError("submission archive must end with .tar.gz or .tgz")

    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        names: list[str] = []
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise SubmissionContractError(f"unsafe archive member: {member.name}")
            if not member.isfile():
                raise SubmissionContractError(
                    f"archive must contain files only: {member.name}"
                )
            names.append(name.as_posix())

        expected_names = list(ARCHIVE_FILE_ORDER)
        if names != expected_names:
            raise SubmissionContractError(
                "archive member order/layout mismatch: "
                f"expected={expected_names}, actual={names}"
            )
        if len(names) != len(set(names)):
            raise SubmissionContractError("duplicate archive member detected")

        if expected_root is not None:
            expected_root = expected_root.resolve()
            for member, relative in zip(members, ARCHIVE_FILE_ORDER, strict=True):
                stream = archive.extractfile(member)
                if stream is None:
                    raise SubmissionContractError(
                        f"archive member unreadable: {member.name}"
                    )
                if stream.read() != (expected_root / relative).read_bytes():
                    raise SubmissionContractError(
                        f"archive content drift: {relative}"
                    )

    return {
        "archive": "PASS",
        "path": str(archive_path),
        "files": names,
        "root_entry": names[0],
    }


def _stage_runtime(cg_dir: Path, stage: Path) -> None:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    for name in ROOT_FILE_ORDER:
        shutil.copy2(ROOT / name, stage / name)

    black_engine = stage / "black_engine"
    black_engine.mkdir()
    for name in BLACK_ENGINE_FILE_ORDER:
        source = ROOT / "black_engine" / name
        target = black_engine / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    cg_target = stage / "cg"
    cg_target.mkdir()
    for name in REQUIRED_CG_FILES:
        source = cg_dir / name
        if not source.is_file():
            raise FileNotFoundError(f"official cg missing: {source}")
        shutil.copy2(source, cg_target / name)


def build(cg_dir: Path, out_archive: Path) -> Path:
    cg_dir = cg_dir.resolve()
    out_archive = out_archive.resolve()
    if not _is_tar_gz(out_archive):
        raise SubmissionContractError("--out must be a .tar.gz or .tgz path")

    validate_source_layout(ROOT)
    out_archive.parent.mkdir(parents=True, exist_ok=True)
    work = out_archive.parent / f".{out_archive.name}.build"
    stage = work / "root"

    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    try:
        _stage_runtime(cg_dir, stage)
        validate_archive_layout(stage)

        with tarfile.open(out_archive, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            for relative in ARCHIVE_FILE_ORDER:
                archive.add(
                    stage / relative,
                    arcname=relative,
                    recursive=False,
                    filter=_normalized_tarinfo,
                )

        inspect_archive(out_archive, expected_root=stage)
        return out_archive
    except Exception:
        out_archive.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cg-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()

    if args.check is not None:
        if args.cg_dir is not None or args.out is not None:
            parser.error("--check cannot be combined with --cg-dir or --out")
        print(inspect_archive(args.check))
        return 0

    if args.cg_dir is None:
        parser.error("--cg-dir is required when building")
    out = args.out or (ROOT / "artifacts" / "submission.tar.gz")
    print(build(args.cg_dir, out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
