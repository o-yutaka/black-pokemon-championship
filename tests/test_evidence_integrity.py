from __future__ import annotations

import json
from pathlib import Path

import pytest

from black_engine.evaluation.models import GameRecord, RuntimeCounters
from black_engine.evaluation.official_runner import summarize
from black_engine.evaluation.promotion import load_summaries


def _write_matchup(root: Path, *, tamper: bool = False) -> None:
    directory = root / "mirror"
    directory.mkdir(parents=True)
    records = [
        GameRecord("mirror", "candidate", "opponent", seat, seat, "DONE", 10, [1.0], RuntimeCounters(completed=1))
        for seat in (0, 1)
    ]
    (directory / "games.jsonl").write_text(
        "".join(json.dumps(record.to_dict()) + "\n" for record in records)
    )
    summary = summarize("mirror", records, engine_sha256="engine").to_dict()
    if tamper:
        summary["wins"] = 99
    (directory / "summary.json").write_text(json.dumps(summary))


def test_load_summaries_recomputes_raw_game_evidence(tmp_path: Path):
    _write_matchup(tmp_path)
    assert load_summaries(tmp_path)["mirror"]["wins"] == 2


def test_load_summaries_rejects_tampered_summary(tmp_path: Path):
    _write_matchup(tmp_path, tamper=True)
    with pytest.raises(ValueError, match="summary/games evidence mismatch"):
        load_summaries(tmp_path)
