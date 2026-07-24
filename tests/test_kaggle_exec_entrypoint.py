from __future__ import annotations

from pathlib import Path

import pytest

from scripts.static_gate import EntrypointContractError, assert_exec_compatible_entrypoint


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_main_is_kaggle_exec_compatible() -> None:
    assert_exec_compatible_entrypoint(ROOT / "main.py")


def test_direct_dunder_file_access_is_rejected(tmp_path: Path) -> None:
    entrypoint = tmp_path / "main.py"
    entrypoint.write_text(
        "from pathlib import Path\nROOT = Path(__file__).resolve().parent\n",
        encoding="utf-8",
    )

    with pytest.raises(EntrypointContractError, match="direct __file__ access"):
        assert_exec_compatible_entrypoint(entrypoint)


def test_optional_globals_lookup_is_allowed(tmp_path: Path) -> None:
    entrypoint = tmp_path / "main.py"
    entrypoint.write_text(
        "module_file = globals().get('__file__')\n",
        encoding="utf-8",
    )

    assert_exec_compatible_entrypoint(entrypoint)


def test_environment_specific_absolute_path_is_rejected(tmp_path: Path) -> None:
    entrypoint = tmp_path / "main.py"
    entrypoint.write_text(
        "BUNDLE_ROOT = '/kaggle_simulations/agent'\n",
        encoding="utf-8",
    )

    with pytest.raises(EntrypointContractError, match="absolute path"):
        assert_exec_compatible_entrypoint(entrypoint)
