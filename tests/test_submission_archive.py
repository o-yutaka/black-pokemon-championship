from __future__ import annotations

import json
import subprocess
import sys
import tarfile
from pathlib import Path

from scripts.build_submission import build, inspect_archive
from submission_contract import (
    ARCHIVE_FILE_ORDER,
    REQUIRED_CG_FILES,
    validate_archive_layout,
)


def _fake_cg(root: Path) -> Path:
    root.mkdir()
    for name in REQUIRED_CG_FILES:
        path = root / name
        if name == "libcg.so":
            path.write_bytes(b"test-libcg-placeholder")
        else:
            path.write_text("# test fixture\n", encoding="utf-8")
    return root


def test_archive_is_rooted_ordered_and_executable_without_file(tmp_path: Path):
    archive_path = build(
        _fake_cg(tmp_path / "cg"),
        tmp_path / "submission.tar.gz",
    )

    report = inspect_archive(archive_path)
    assert report["files"] == list(ARCHIVE_FILE_ORDER)
    assert report["root_entry"] == "main.py"
    assert all(not name.startswith("submission/") for name in report["files"])

    extracted = tmp_path / "extracted"
    extracted.mkdir()
    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(extracted, filter="data")

    validate_archive_layout(extracted)

    probe = r'''
import json
from pathlib import Path

namespace = {"__name__": "submission_bundle"}
source = Path("main.py").read_text(encoding="utf-8")
exec(compile(source, "main.py", "exec"), namespace)

step0 = namespace["agent"]({
    "current": None,
    "select": None,
    "search_begin_input": None,
})
step1 = namespace["agent"]({
    "current": {"yourIndex": 0, "players": []},
    "select": {
        "context": 0,
        "minCount": 1,
        "maxCount": 1,
        "option": [{"type": 14}],
    },
})
print(json.dumps({"step0": step0, "step1": step1}))
'''
    completed = subprocess.run(
        [sys.executable, "-I", "-c", probe],
        cwd=extracted,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert len(result["step0"]) == 60
    assert result["step1"] == [0]
