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

from artifact_store import BundleArtifact, EngineArtifact
from official_replay_adapter import normalize_official_frame


class EngineRuntimeError(RuntimeError):
    pass


class StartData(ctypes.Structure):
    _fields_ = [("battlePtr", ctypes.c_void_p), ("errorPlayer", ctypes.c_int), ("errorType", ctypes.c_int)]


class SerialData(ctypes.Structure):
    _fields_ = [("json", ctypes.c_char_p), ("data", ctypes.c_char_p), ("count", ctypes.c_int), ("selectPlayer", ctypes.c_int)]


def _legalize(obs: dict[str, Any], value: Any) -> list[int]:
    select = obs.get("select") or {}
    options = select.get("option") or []
    minimum = int(select.get("minCount", 0) or 0)
    maximum_raw = select.get("maxCount", minimum)
    maximum = minimum if maximum_raw is None else int(maximum_raw)
    values = [value] if isinstance(value, int) and not isinstance(value, bool) else list(value) if isinstance(value, (list, tuple)) else []
    if any(not isinstance(index, int) or isinstance(index, bool) for index in values):
        values = []
    invalid = len(values) != len(set(values)) or not minimum <= len(values) <= maximum or any(index < 0 or index >= len(options) for index in values)
    return list(range(minimum)) if invalid and minimum <= len(options) else ([] if invalid else values)


class AgentProcess:
    def __init__(self, bundle: BundleArtifact, timeout_seconds: float = 5.0) -> None:
        worker = Path(__file__).with_name("agent_worker.py")
        env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
        env["BLACK_BUNDLE_ROOT"] = str(bundle.root)
        self.process = subprocess.Popen(
            [sys.executable, "-I", str(worker), str(bundle.root)], cwd=bundle.root, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        self.timeout_seconds = timeout_seconds
        self.lock = threading.Lock()
        ready = self._readline(timeout_seconds)
        if not ready.get("ready"):
            self.close()
            raise EngineRuntimeError(f"agent bootstrap failed: {ready.get('error', 'unknown error')}")

    def _readline(self, timeout: float) -> dict[str, Any]:
        if self.process.stdout is None:
            raise EngineRuntimeError("agent stdout unavailable")
        selector = selectors.DefaultSelector()
        selector.register(self.process.stdout, selectors.EVENT_READ)
        events = selector.select(timeout)
        selector.close()
        if not events:
            raise EngineRuntimeError("agent response timeout")
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read()[-2000:] if self.process.stderr else ""
            raise EngineRuntimeError(f"agent process exited: {stderr}")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise EngineRuntimeError(f"invalid agent response: {line[:500]}") from exc

    def decide(self, observation: dict[str, Any]) -> tuple[list[int], float, str | None]:
        if self.process.stdin is None:
            raise EngineRuntimeError("agent stdin unavailable")
        started = time.perf_counter()
        with self.lock:
            self.process.stdin.write(json.dumps({"observation": observation, "configuration": None}, separators=(",", ":")) + "\n")
            self.process.stdin.flush()
            response = self._readline(self.timeout_seconds)
        elapsed = (time.perf_counter() - started) * 1000.0
        proposed = response.get("selection") if response.get("ok") else []
        error = None if response.get("ok") else str(response.get("error", "agent error"))
        return _legalize(observation, proposed), elapsed, error

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()


class OfficialLibrary:
    def __init__(self, artifact: EngineArtifact) -> None:
        self.artifact = artifact
        self.lib = ctypes.CDLL(str(artifact.library_path))
        self.lib.GameInitialize.argtypes = []
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
        self.lib.AllCard.argtypes = []
        self.lib.AllCard.restype = ctypes.c_char_p
        self.lib.AllAttack.argtypes = []
        self.lib.AllAttack.restype = ctypes.c_char_p
        self.lib.GameInitialize()

    def all_cards(self) -> list[dict[str, Any]]:
        return json.loads(self.lib.AllCard().decode("utf-8"))

    def all_attacks(self) -> list[dict[str, Any]]:
        return json.loads(self.lib.AllAttack().decode("utf-8"))


@dataclass
class DecisionEvidence:
    actor: int
    selection: list[int]
    elapsed_ms: float
    error: str | None


class OfficialBattleSession:
    name = "official-cabt-uploaded-bundles"

    def __init__(self, engine: EngineArtifact, bundles: tuple[BundleArtifact, BundleArtifact]) -> None:
        self.library = OfficialLibrary(engine)
        self.bundles = bundles
        self.agents = (AgentProcess(bundles[0]), AgentProcess(bundles[1]))
        array = (ctypes.c_int * 120)(*(list(bundles[0].deck) + list(bundles[1].deck)))
        start = self.library.lib.BattleStart(array)
        if not start.battlePtr or start.errorType:
            for agent in self.agents:
                agent.close()
            raise EngineRuntimeError(f"BattleStart failed player={start.errorPlayer} errorType={start.errorType}")
        self.pointer = start.battlePtr
        self.frame_id = 0
        self.finished = False
        self.last_frame: dict[str, Any] | None = None
        self.last_decision: DecisionEvidence | None = None

    async def start(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._snapshot)

    def _get_observation(self) -> tuple[dict[str, Any], int]:
        data = self.library.lib.GetBattleData(self.pointer)
        if not data.json:
            raise EngineRuntimeError("GetBattleData returned no JSON")
        return json.loads(data.json.decode("utf-8")), int(data.selectPlayer)

    def _normalized_visual(self) -> dict[str, Any]:
        raw = self.library.lib.VisualizeData(self.pointer)
        if not raw:
            raise EngineRuntimeError("VisualizeData returned no JSON")
        frames = json.loads(raw.decode("utf-8"))
        visual = dict(frames[-1]) if frames else self._get_observation()[0]
        if self.last_decision is not None:
            visual["decision"] = {
                "actor": self.last_decision.actor, "goal": "uploaded_bundle_agent", "chosen": str(self.last_decision.selection),
                "confidence": None, "elapsedMs": self.last_decision.elapsed_ms,
                "candidates": [{"label": str(self.last_decision.selection), "score": 1.0, "selected": True}],
            }
            if self.last_decision.error:
                visual.setdefault("logs", []).append({"type": "agent_error", "playerIndex": self.last_decision.actor, "text": self.last_decision.error})
        frame = normalize_official_frame(visual, self.frame_id)
        frame["players"][0]["name"] = self.bundles[0].filename
        frame["players"][1]["name"] = self.bundles[1].filename
        self.finished = frame.get("result") is not None
        self.last_frame = frame
        return frame

    def _snapshot(self) -> dict[str, Any]:
        return self._normalized_visual()

    async def step(self, _selection: list[int] | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._step_sync)

    def _step_sync(self) -> dict[str, Any]:
        if self.finished:
            raise ValueError("battle already finished")
        observation, player = self._get_observation()
        selection, elapsed, error = self.agents[player].decide(observation)
        array = (ctypes.c_int * len(selection))(*selection) if selection else None
        code = int(self.library.lib.Select(self.pointer, array, len(selection)))
        if code:
            raise EngineRuntimeError(f"official Select rejected player={player} selection={selection} code={code}")
        self.frame_id += 1
        self.last_decision = DecisionEvidence(player, selection, elapsed, error)
        return self._normalized_visual()

    def legal_selections(self) -> list[list[int]]:
        return [] if self.finished else [[0]]

    async def close(self) -> None:
        await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        if getattr(self, "pointer", None):
            self.library.lib.BattleFinish(self.pointer)
            self.pointer = None
        for agent in self.agents:
            agent.close()
