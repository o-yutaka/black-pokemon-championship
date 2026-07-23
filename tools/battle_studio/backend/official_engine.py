from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any


class OfficialEngineError(RuntimeError):
    pass


class OfficialProcessEngine:
    """JSONL bridge to the WSL2 process that owns official cg/libcg.so execution."""

    name = "official-cabt"

    def __init__(self, player_root: Path, opponent_root: Path | None = None) -> None:
        self.player_root = player_root
        self.opponent_root = opponent_root
        self.proc: asyncio.subprocess.Process | None = None
        self._legal: list[list[int]] = []

    async def start(self) -> dict[str, Any]:
        runner = os.environ.get("BLACK_OFFICIAL_RUNNER")
        if not runner:
            raise OfficialEngineError("BLACK_OFFICIAL_RUNNER is not configured")
        args = [runner, "--player-bundle", str(self.player_root)]
        if self.opponent_root:
            args += ["--opponent-bundle", str(self.opponent_root)]
        self.proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.player_root),
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        return await self._request({"type": "start"})

    async def step(self, selection: list[int]) -> dict[str, Any]:
        return await self._request({"type": "step", "selection": selection})

    def legal_selections(self) -> list[list[int]]:
        return self._legal

    async def close(self) -> None:
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                self.proc.kill()
                await self.proc.wait()

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.proc or not self.proc.stdin or not self.proc.stdout:
            raise OfficialEngineError("official runner is not started")
        self.proc.stdin.write((json.dumps(payload, separators=(",", ":")) + "\n").encode())
        await self.proc.stdin.drain()
        try:
            line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=30)
        except asyncio.TimeoutError as exc:
            raise OfficialEngineError("official runner timeout") from exc
        if not line:
            detail = ""
            if self.proc.stderr:
                detail = (await self.proc.stderr.read()).decode(errors="replace")[-2000:]
            raise OfficialEngineError(f"official runner exited: {detail}")
        message = json.loads(line)
        if message.get("type") == "error":
            raise OfficialEngineError(str(message.get("detail") or message.get("code")))
        frame = message.get("frame")
        if not isinstance(frame, dict):
            raise OfficialEngineError("runner response missing frame")
        legal = message.get("legalSelections", [])
        self._legal = [x for x in legal if isinstance(x, list) and all(isinstance(i, int) for i in x)]
        return frame
