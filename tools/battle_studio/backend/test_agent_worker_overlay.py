from __future__ import annotations

import unittest
from types import SimpleNamespace

from agent_worker import collect_overlay


class AgentWorkerOverlayTest(unittest.TestCase):
    def test_prefers_explicit_overlay(self) -> None:
        module = SimpleNamespace(BLACK_DECISION_OVERLAY={"goal": "stale"})
        overlay = collect_overlay(module, lambda *_: [0], {}, [0], {"goal": "explicit"})
        self.assertEqual(overlay, {"goal": "explicit"})

    def test_reads_hook_without_changing_agent_selection_contract(self) -> None:
        module = SimpleNamespace(get_black_decision_overlay=lambda: {"scores": {"total": 72}})
        overlay = collect_overlay(module, lambda *_: [3], {"select": {}}, [3], None)
        self.assertEqual(overlay["scores"]["total"], 72)

    def test_consumes_module_overlay_once(self) -> None:
        module = SimpleNamespace(BLACK_DECISION_OVERLAY={"warnings": ["test"]})
        overlay = collect_overlay(module, lambda *_: [0], {}, [0], None)
        self.assertEqual(overlay["warnings"], ["test"])
        self.assertIsNone(module.BLACK_DECISION_OVERLAY)


if __name__ == "__main__":
    unittest.main()
