from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
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

    def test_isolated_worker_boots_and_returns_side_channel_overlay(self) -> None:
        worker = Path(__file__).with_name("agent_worker.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "main.py").write_text(
                "BLACK_DECISION_OVERLAY = None\n"
                "def agent(observation, configuration):\n"
                "    global BLACK_DECISION_OVERLAY\n"
                "    BLACK_DECISION_OVERLAY = {'scores': {'total': 7}, 'warnings': ['isolated']}\n"
                "    return [0]\n",
                encoding="utf-8",
            )
            process = subprocess.Popen(
                [sys.executable, "-I", str(worker), str(root)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            try:
                self.assertIsNotNone(process.stdout)
                self.assertIsNotNone(process.stdin)
                ready = json.loads(process.stdout.readline())
                self.assertTrue(ready["ready"])
                request = {"observation": {"select": {"option": [{"kind": "PASS"}], "minCount": 1, "maxCount": 1}}, "configuration": None}
                process.stdin.write(json.dumps(request) + "\n")
                process.stdin.flush()
                response = json.loads(process.stdout.readline())
                self.assertEqual(response["selection"], [0])
                self.assertEqual(response["overlay"]["scores"]["total"], 7)
                self.assertEqual(response["overlay"]["warnings"], ["isolated"])
            finally:
                process.terminate()
                process.wait(timeout=2)
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()


if __name__ == "__main__":
    unittest.main()
