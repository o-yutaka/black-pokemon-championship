from __future__ import annotations

import asyncio
import ctypes
import json
import os
import selectors
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from decision_ide_contract import normalize_ide_fields
from decision_overlay import build_board_diff, normalize_decision_overlay
from native_artifacts import BundleArtifact, EngineArtifact
from official_replay_adapter import normalize_official_frame


class NativeEngineError(RuntimeError):
    pass


class StartData(ctypes.Structure):
    _fields_ = [("battlePtr", ctypes.c_void_p), ("errorPlayer", ctypes.c_int), ("errorType", ctypes.c_int)]


class SerialData(ctypes.Structure):
    _fields_ = [("json", ctypes.c_char_p), ("data", ctypes.c_char_p), ("count", ctypes.c_int), ("selectPlayer", ctypes.c_int)]


def _legalize(obs: dict[str, Any], value: Any) -> list[int]:
    select = obs.get("select") or {}
    options = select.get("option") or []
    minimum = int(select.get("minCount", 0) or 0)
    maximum = int(select.get("maxCount", minimum) if select.get("maxCount") is not None else minimum)
    values = [value] if isinstance(value, int) and not isinstance(value, bool) else list(value) if isinstance(value, (list, tuple)) else []
    invalid = any(not isinstance(index, int) or isinstance(index, bool) for index in values) or len(values) != len(set(values)) or not minimum <= len(values) <= maximum or any(index < 0 or index >= len(options) for index in values)
    return list(range(minimum)) if invalid and minimum <= len(options) else ([] if invalid else values)


class AgentProcess:
    def __init__(self, bundle: BundleArtifact, timeout_seconds: float = 5.0) -> None:
        worker = Path(__file__).with_name("agent_worker.py")
        env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
        self.process = subprocess.Popen([sys.executable, "-I", str(worker), str(bundle.root)], cwd=bundle.root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        self.timeout_seconds = timeout_seconds
        self.lock = threading.Lock()
        ready = self._readline(timeout_seconds)
        if not ready.get("ready"):
            self.close()
            raise NativeEngineError(f"agent bootstrap failed: {ready.get('error', 'unknown error')}")
        self.overlay_protocol = str(ready.get("overlayProtocol", "legacy"))

    def _readline(self, timeout: float) -> dict[str, Any]:
        if self.process.stdout is None:
            raise NativeEngineError("agent stdout unavailable")
        selector = selectors.DefaultSelector()
        selector.register(self.process.stdout, selectors.EVENT_READ)
        events = selector.select(timeout)
        selector.close()
        if not events:
            raise NativeEngineError("agent response timeout")
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read()[-2000:] if self.process.stderr else ""
            raise NativeEngineError(f"agent process exited: {stderr}")
        return json.loads(line)

    def decide(self, observation: dict[str, Any]) -> tuple[list[int], float, str | None, dict[str, Any] | None]:
        if self.process.stdin is None:
            raise NativeEngineError("agent stdin unavailable")
        started = time.perf_counter()
        with self.lock:
            self.process.stdin.write(json.dumps({"observation": observation, "configuration": None}, separators=(",", ":")) + "\n")
            self.process.stdin.flush()
            response = self._readline(self.timeout_seconds)
        elapsed = (time.perf_counter() - started) * 1000.0
        proposed = response.get("selection") if response.get("ok") else []
        overlay = response.get("overlay") if isinstance(response.get("overlay"), dict) else None
        return _legalize(observation, proposed), elapsed, None if response.get("ok") else str(response.get("error", "agent error")), overlay

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()


@dataclass
class DecisionEvidence:
    actor: int
    selection: list[int]
    elapsed_ms: float
    error: str | None
    overlay: dict[str, Any]


class NativeOfficialBattleSession:
    name = "official-cabt-uploaded-bundles"

    def __init__(self, engine: EngineArtifact, bundles: tuple[BundleArtifact, BundleArtifact]) -> None:
        self.engine = engine
        self.bundles = bundles
        self.lib = ctypes.CDLL(str(engine.library_path))
        self.lib.GameInitialize.restype = None
        self.lib.BattleStart.argtypes = [ctypes.POINTER(ctypes.c_int)]
        self.lib.BattleStart.restype = StartData
        self.lib.GetBattleData.argtypes = [ctypes.c_void_p]
        self.lib.GetBattleData.restype = SerialData
        self.lib.Select.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.c_int]
        self.lib.Select.restype = ctypes.c_int
        self.lib.VisualizeData.argtypes = [ctypes.c_void_p]
        self.lib.VisualizeData.restype = ctypes.c_char_p
        self.lib.BattleFinish.argtypes = [ctypes.c_void_p]
        self.lib.BattleFinish.restype = None
        self.lib.GameInitialize()
        self.agents = (AgentProcess(bundles[0]), AgentProcess(bundles[1]))
        deck_array = (ctypes.c_int * 120)(*(list(bundles[0].deck) + list(bundles[1].deck)))
        start = self.lib.BattleStart(deck_array)
        if not start.battlePtr or start.errorType:
            for agent in self.agents:
                agent.close()
            raise NativeEngineError(f"BattleStart failed player={start.errorPlayer} errorType={start.errorType}")
        self.pointer = start.battlePtr
        self.frame_id = 0
        self.finished = False
        self.last_decision: DecisionEvidence | None = None

    async def start(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._snapshot)

    def _observation(self) -> tuple[dict[str, Any], int]:
        data = self.lib.GetBattleData(self.pointer)
        if not data.json:
            raise NativeEngineError("GetBattleData returned no JSON")
        return json.loads(data.json.decode("utf-8")), int(data.selectPlayer)

    def _visual(self) -> dict[str, Any]:
        raw = self.lib.VisualizeData(self.pointer)
        if not raw:
            raise NativeEngineError("VisualizeData returned no JSON")
        frames = json.loads(raw.decode("utf-8"))
        return dict(frames[-1]) if frames else self._observation()[0]

    def _snapshot(self, visual: dict[str, Any] | None = None) -> dict[str, Any]:
        frame = normalize_official_frame(visual or self._visual(), self.frame_id)
        if self.last_decision:
            decision = dict(self.last_decision.overlay)
            decision["actor"] = self.last_decision.actor
            decision["elapsedMs"] = self.last_decision.elapsed_ms
            frame["decision"] = decision
            if self.last_decision.error:
                frame.setdefault("events", []).append({"type": "agent_error", "actor": self.last_decision.actor, "text": self.last_decision.error, "cardKey": None})
        frame["players"][0]["name"] = self.bundles[0].filename
        frame["players"][1]["name"] = self.bundles[1].filename
        self.finished = frame.get("result") is not None
        return frame

    async def step(self, _selection: list[int]) -> dict[str, Any]:
        return await asyncio.to_thread(self._step_sync)

    def _step_sync(self) -> dict[str, Any]:
        if self.finished:
            raise NativeEngineError("battle already finished")
        before_visual = self._visual()
        before_frame = normalize_official_frame(before_visual, self.frame_id)
        observation, player = self._observation()
        selection, elapsed, error, explicit_overlay = self.agents[player].decide(observation)
        decision = normalize_decision_overlay(observation, selection, elapsed, error, explicit_overlay)
        decision.update(normalize_ide_fields(explicit_overlay or {}, decision.get("candidates", [])))
        array = (ctypes.c_int * len(selection))(*selection) if selection else None
        code = int(self.lib.Select(self.pointer, array, len(selection)))
        if code:
            raise NativeEngineError(f"official Select rejected player={player} selection={selection} code={code}")
        self.frame_id += 1
        after_visual = self._visual()
        after_frame = normalize_official_frame(after_visual, self.frame_id)
        decision["boardDiff"] = [*decision.get("boardDiff", []), *build_board_diff(before_frame, after_frame)]
        self.last_decision = DecisionEvidence(player, selection, elapsed, error, decision)
        return self._snapshot(after_visual)

    def legal_selections(self) -> list[list[int]]:
        return [] if self.finished else [[0]]

    async def close(self) -> None:
        await asyncio.to_thread(self._close)

    def _close(self) -> None:
        if getattr(self, "pointer", None):
            self.lib.BattleFinish(self.pointer)
            self.pointer = None
        for agent in self.agents:
            agent.close()
