from __future__ import annotations

import ast
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class EntrypointContractError(RuntimeError):
    """Raised when a submission entrypoint cannot run under Kaggle raw exec()."""


def assert_exec_compatible_entrypoint(path: Path) -> None:
    """Reject entrypoints that require Python's normal module-file context.

    Kaggle CABT evaluates ``main.py`` with ``exec(code_object, env)``. In that
    environment ``__file__`` is not guaranteed to exist. Access through
    ``globals().get('__file__')`` remains valid because it is optional; a direct
    ``Name('__file__')`` expression is not.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    direct_file_reads = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and node.id == "__file__"
        and isinstance(node.ctx, ast.Load)
    ]
    if direct_file_reads:
        lines = ", ".join(str(line) for line in sorted(direct_file_reads))
        raise EntrypointContractError(
            f"{path}: direct __file__ access is forbidden for Kaggle exec(); lines={lines}"
        )

    hard_coded_absolute_paths: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        value = node.value
        if value.startswith(("/kaggle/", "/kaggle_simulations/", "/home/", "/tmp/")):
            hard_coded_absolute_paths.append((node.lineno, value))

    if hard_coded_absolute_paths:
        detail = ", ".join(f"line {line}: {value}" for line, value in hard_coded_absolute_paths)
        raise EntrypointContractError(
            f"{path}: environment-specific absolute path is forbidden; {detail}"
        )


def main() -> int:
    from scripts.build_submission import build, inspect_archive
    from submission_contract import REQUIRED_CG_FILES, validate_archive_layout, validate_source_layout

    source = validate_source_layout(ROOT)
    assert_exec_compatible_entrypoint(ROOT / "main.py")

    with tempfile.TemporaryDirectory(prefix="dragapult_submission_gate_") as raw:
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
        assert_exec_compatible_entrypoint(extracted / "main.py")

        probe = r'''
import json
from pathlib import Path

# Match kaggle_environments.agent.get_last_callable: no __file__ injected.
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
            raise RuntimeError(
                "isolated extracted-bundle execution failed: "
                + process.stderr
            )
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
                "kaggle_exec_contract": {
                    "direct___file__": "forbidden",
                    "environment_absolute_paths": "forbidden",
                    "raw_exec_without___file__": "passed",
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
