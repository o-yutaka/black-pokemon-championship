from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.build_official_hybrid_submission import build, stage_submission
from submission_contract import (
    CANDIDATE,
    REQUIRED_CG_FILES,
    SubmissionContractError,
    validate_runtime_layout,
    validate_source_layout,
)

ROOT = Path(__file__).resolve().parents[1]


def _fake_cg(root: Path) -> Path:
    cg = root / "cg"
    cg.mkdir(parents=True)
    for name in REQUIRED_CG_FILES:
        path = cg / name
        if name == "libcg.so":
            path.write_bytes(b"NONEMPTY_LAYOUT_TEST_LIBRARY")
        else:
            path.write_text("# layout test fixture\n", encoding="utf-8")
    return cg


def _isolated_import(directory: Path) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = ""
    environment["PYTHONNOUSERSITE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "import main; assert len(main.agent(None, None)) == 60; print(main.CANDIDATE)",
        ],
        cwd=directory,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_repository_root_is_the_canonical_submission_source():
    report = validate_source_layout(ROOT)
    assert report["candidate"] == CANDIDATE
    assert report["deck_total"] == 60
    assert (ROOT / "deck.csv").read_bytes() == (
        ROOT / "candidates" / CANDIDATE / "deck.csv"
    ).read_bytes()


def test_root_main_refuses_to_open_without_complete_runtime_layout():
    completed = _isolated_import(ROOT)
    assert completed.returncode != 0
    assert "submission runtime layout missing cg/" in completed.stderr


def test_staged_submission_is_byte_identical_and_opens_in_isolation(tmp_path: Path):
    cg = _fake_cg(tmp_path)
    staged = stage_submission(cg, tmp_path / "submission")
    report = validate_runtime_layout(staged)
    assert report["runtime"] == "PASS"
    for name in ("main.py", "deck.csv", "submission_contract.py"):
        assert (ROOT / name).read_bytes() == (staged / name).read_bytes()
    completed = _isolated_import(staged)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip().splitlines()[-1] == CANDIDATE


def test_runtime_layout_rejects_missing_or_empty_engine(tmp_path: Path):
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    for name in ("main.py", "deck.csv", "black_lab.py", "submission_contract.py"):
        (incomplete / name).write_bytes((ROOT / name).read_bytes())
    (incomplete / "black_engine").mkdir()
    with pytest.raises(SubmissionContractError, match="missing cg"):
        validate_runtime_layout(incomplete)

    cg = incomplete / "cg"
    cg.mkdir()
    for name in REQUIRED_CG_FILES:
        (cg / name).write_bytes(b"" if name == "libcg.so" else b"# fixture\n")
    with pytest.raises(SubmissionContractError, match="libcg.so is empty"):
        validate_runtime_layout(incomplete)


def test_builder_is_locked_to_the_canonical_candidate(tmp_path: Path):
    cg = _fake_cg(tmp_path)
    with pytest.raises(ValueError, match="submission-locked"):
        build("mewtwo_spidops", cg, tmp_path / "wrong.zip")
