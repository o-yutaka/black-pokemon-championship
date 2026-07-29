from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from runtime_truth import _active_sessions, build_health


class RuntimeTruthTests(unittest.TestCase):
    def test_active_sessions_separate_emulator_and_official_kinds(self) -> None:
        sessions = {
            "emu": SimpleNamespace(engine=SimpleNamespace(name="cabt-shape-emulator"), public_view=None, public_advance=None),
            "process": SimpleNamespace(engine=SimpleNamespace(name="official"), public_view=object(), public_advance="legal-first"),
            "native": SimpleNamespace(engine=SimpleNamespace(name="official-native"), public_view=object(), public_advance="agent"),
        }
        self.assertEqual(
            _active_sessions(sessions),
            {"total": 3, "emulator": 1, "officialProcess": 1, "officialNative": 1, "unknown": 0},
        )

    def test_health_separates_capability_runtime_and_build_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dist = Path(temp) / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
            fake = SimpleNamespace(
                FRONTEND_DIST=dist,
                NATIVE=SimpleNamespace(engines={}, bundles={}),
                SESSIONS={},
                PUBLIC_PROTOCOL_VERSION="1.1",
                _runner_available=lambda: False,
                _simulator_view_available=lambda: True,
                _card_catalog_available=lambda: True,
            )
            env = {
                "BLACK_FRONTEND_BUILD_HEAD": "a" * 40,
                "BLACK_FRONTEND_BUILD_BRANCH": "main",
                "BLACK_FRONTEND_BUILD_DIRTY": "0",
                "BLACK_FRONTEND_BUILT_AT": "2026-07-30T00:00:00Z",
            }
            with patch.dict(os.environ, env, clear=False), patch(
                "runtime_truth._runtime_git",
                return_value={
                    "repoRoot": "/repo",
                    "branch": "main",
                    "head": "a" * 40,
                    "dirty": False,
                    "dirtyEntryCount": 0,
                },
            ):
                health = build_health(fake)

        self.assertFalse(health["capabilities"]["officialSessionStartAvailable"])
        self.assertTrue(health["capabilities"]["emulatorAvailable"])
        self.assertEqual(health["activeSessions"]["total"], 0)
        self.assertTrue(health["runtime"]["frontendBuild"]["matchesRuntimeWorktree"])
        self.assertIn("OFFICIAL_RUNTIME_UNAVAILABLE", health["warnings"])
        self.assertTrue(health["legacyFieldsDeprecated"])
        self.assertFalse(health["officialCabt"])


if __name__ == "__main__":
    unittest.main()
