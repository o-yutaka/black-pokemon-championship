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

    def _fake_runtime(self, dist: Path) -> SimpleNamespace:
        return SimpleNamespace(
            FRONTEND_DIST=dist,
            NATIVE=SimpleNamespace(engines={}, bundles={}),
            SESSIONS={},
            PUBLIC_PROTOCOL_VERSION="1.1",
            _runner_available=lambda: False,
            _simulator_view_available=lambda: True,
            _card_catalog_available=lambda: True,
        )

    def test_health_separates_capability_runtime_and_build_provenance(self) -> None:
        fingerprint = "f" * 64
        with tempfile.TemporaryDirectory() as temp:
            dist = Path(temp) / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
            env = {
                "BLACK_FRONTEND_BUILD_HEAD": "a" * 40,
                "BLACK_FRONTEND_BUILD_BRANCH": "main",
                "BLACK_FRONTEND_BUILD_DIRTY": "0",
                "BLACK_FRONTEND_BUILD_FINGERPRINT": fingerprint,
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
                    "worktreeFingerprint": fingerprint,
                },
            ):
                health = build_health(self._fake_runtime(dist))

        self.assertFalse(health["capabilities"]["officialSessionStartAvailable"])
        self.assertTrue(health["capabilities"]["emulatorAvailable"])
        self.assertEqual(health["activeSessions"]["total"], 0)
        self.assertTrue(health["runtime"]["frontendBuild"]["matchesRuntimeWorktree"])
        self.assertEqual(health["healthSchemaVersion"], "2.1")
        self.assertEqual(health["fieldSemantics"]["emulator"], "capability_available_not_active_session")
        self.assertIn("OFFICIAL_RUNTIME_UNAVAILABLE", health["warnings"])
        self.assertTrue(health["legacyFieldsDeprecated"])
        self.assertFalse(health["officialCabt"])

    def test_same_head_and_dirty_flag_do_not_hide_changed_dirty_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dist = Path(temp) / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("ok", encoding="utf-8")
            env = {
                "BLACK_FRONTEND_BUILD_HEAD": "a" * 40,
                "BLACK_FRONTEND_BUILD_BRANCH": "main",
                "BLACK_FRONTEND_BUILD_DIRTY": "1",
                "BLACK_FRONTEND_BUILD_FINGERPRINT": "1" * 64,
                "BLACK_FRONTEND_BUILT_AT": "2026-07-30T00:00:00Z",
            }
            with patch.dict(os.environ, env, clear=False), patch(
                "runtime_truth._runtime_git",
                return_value={
                    "repoRoot": "/repo",
                    "branch": "main",
                    "head": "a" * 40,
                    "dirty": True,
                    "dirtyEntryCount": 2,
                    "worktreeFingerprint": "2" * 64,
                },
            ):
                health = build_health(self._fake_runtime(dist))

        self.assertFalse(health["runtime"]["frontendBuild"]["matchesRuntimeWorktree"])
        self.assertIn("FRONTEND_BUILD_DOES_NOT_MATCH_RUNTIME_WORKTREE", health["warnings"])
        self.assertIn("RUNTIME_WORKTREE_DIRTY", health["warnings"])


if __name__ == "__main__":
    unittest.main()
