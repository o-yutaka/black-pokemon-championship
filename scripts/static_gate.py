from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEARCH_API_TOKENS = (
    "search_begin(",
    "search_step(",
    "search_release(",
    "search_end(",
    ".search_begin(",
    ".search_step(",
    ".search_release(",
    ".search_end(",
)


def _assert_search_api_absent(root: Path) -> None:
    hits: list[str] = []
    for path in [root / "main.py", *(root / "black_engine").rglob("*.py")]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in SEARCH_API_TOKENS:
            if token in text:
                hits.append(f"{path.relative_to(root)}:{token}")
    if hits:
        raise RuntimeError(f"production Search API use requires explicit leak instrumentation: {hits}")


def main() -> int:
    from scripts.build_submission import build, inspect_archive
    from submission_contract import REQUIRED_CG_FILES, validate_archive_layout, validate_source_layout

    source = validate_source_layout(ROOT)
    _assert_search_api_absent(ROOT)
    with tempfile.TemporaryDirectory(prefix="rocket_mewtwo_submission_gate_") as raw:
        temporary = Path(raw)
        cg = temporary / "cg_source"
        cg.mkdir()
        for name in REQUIRED_CG_FILES:
            target = cg / name
            target.write_bytes(b"test-libcg" if name == "libcg.so" else b"# fixture\n")

        archive_path = build(cg, temporary / "submission.tar.gz")
        archive = inspect_archive(archive_path)
        if archive["root_entry"] != "main.py":
            raise RuntimeError("main.py is not the first archive entry")

        extracted = temporary / "extracted"
        extracted.mkdir()
        with tarfile.open(archive_path, "r:gz") as bundle:
            bundle.extractall(extracted, filter="data")
        runtime = validate_archive_layout(extracted)
        _assert_search_api_absent(extracted)

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
}, None)
step1 = namespace["agent"]({
    "current": {"yourIndex": 0, "players": []},
    "select": {
        "context": 0,
        "minCount": 1,
        "maxCount": 1,
        "option": [{"type": 14}],
    },
}, None)
print(json.dumps({"step0": step0, "step1": step1}))
'''
        process = subprocess.run(
            [sys.executable, "-I", "-c", probe],
            cwd=extracted,
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            raise RuntimeError("isolated extracted-bundle execution failed: " + process.stderr)
        payload = json.loads(process.stdout.strip().splitlines()[-1])
        if len(payload.get("step0", [])) != 60:
            raise RuntimeError("deck handshake failed")
        if payload.get("step1") != [0]:
            raise RuntimeError(f"normal action contract failed: {payload.get('step1')}")

    print(
        json.dumps(
            {
                "verdict": "STATIC_GATE_PASS",
                "source": source,
                "runtime": runtime,
                "archive": archive,
                "search_api": "ABSENT_BY_STATIC_GATE",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
