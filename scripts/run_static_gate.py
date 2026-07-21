from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_lab import read_deck, validate_deck
from scripts.build_official_hybrid_submission import stage_submission
from submission_contract import CANDIDATE, REQUIRED_CG_FILES, validate_source_layout


def _make_ci_cg(directory: Path) -> Path:
    cg = directory / "cg"
    cg.mkdir(parents=True)
    for name in REQUIRED_CG_FILES:
        path = cg / name
        if name == "libcg.so":
            path.write_bytes(b"CI_LAYOUT_STUB_NOT_A_RUNTIME_ENGINE")
        else:
            path.write_text("# submission layout fixture\n", encoding="utf-8")
    return cg


def _isolated_submission_handshake(submission: Path) -> dict:
    command = [
        sys.executable,
        "-c",
        (
            "import json, main; "
            "deck=main.agent(None, None); "
            "print(json.dumps({'candidate': main.CANDIDATE, 'deck_total': len(deck), "
            "'runtime_class': type(main.RUNTIME).__name__}))"
        ),
    ]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = ""
    environment["PYTHONNOUSERSITE"] = "1"
    completed = subprocess.run(
        command,
        cwd=submission,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(
            "isolated canonical submission import failed:\n"
            + completed.stdout
            + completed.stderr
        )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    if payload.get("candidate") != CANDIDATE or payload.get("deck_total") != 60:
        raise SystemExit(f"canonical submission handshake mismatch: {payload}")
    return payload


def main() -> int:
    source_report = validate_source_layout(ROOT)
    canonical_deck = read_deck(ROOT / "deck.csv")
    candidate_deck = read_deck(ROOT / "candidates" / CANDIDATE / "deck.csv")
    if canonical_deck != candidate_deck:
        raise SystemExit("canonical deck.csv drifted from candidate metadata deck")

    reports = []
    for name in (
        "mewtwo_spidops",
        "garchomp_spiritomb",
        "dragapult_cinderace",
        "crustle_redteam",
        "grimmsnarl_redteam",
    ):
        directory = ROOT / "candidates" / name
        manifest = json.loads((directory / "manifest.json").read_text())
        deck = read_deck(directory / "deck.csv")
        report = validate_deck(deck, set(manifest["ace_spec_ids"]))
        if not report["ok"]:
            raise SystemExit(report["violations"])
        spec = importlib.util.spec_from_file_location(f"{name}_main", directory / "main.py")
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        if module.agent(None, None) != deck:
            raise SystemExit(f"{name}: handshake mismatch")
        reports.append({**report, "candidate": name, "handshake": "PASS", "official_engine": "UNEXECUTED"})

    with tempfile.TemporaryDirectory(prefix="black_submission_gate_") as temporary:
        temporary_root = Path(temporary)
        cg = _make_ci_cg(temporary_root)
        staged = stage_submission(cg, temporary_root / "submission")
        handshake = _isolated_submission_handshake(staged)
        byte_identity = {
            name: (ROOT / name).read_bytes() == (staged / name).read_bytes()
            for name in ("main.py", "deck.csv", "submission_contract.py")
        }
        if not all(byte_identity.values()):
            raise SystemExit(f"canonical-to-staged byte identity failed: {byte_identity}")

    print(json.dumps({
        "verdict": "SUBMISSION_FIRST_STATIC_GATE_PASS_OFFICIAL_ENGINE_HOLD",
        "submission_source": source_report,
        "submission_handshake": handshake,
        "byte_identity": byte_identity,
        "candidates": reports,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
