from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parent


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(url: str, data: dict | None = None) -> dict:
    body = None if data is None else json.dumps(data).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.loads(response.read())


def main() -> int:
    port = free_port()
    command = [sys.executable, "-m", "uvicorn", "live_server:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"]
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    evidence: dict = {"port": port, "command": command, "checks": []}
    try:
        deadline = time.time() + 10
        health = None
        while time.time() < deadline:
            try:
                health = request_json(f"http://127.0.0.1:{port}/api/health")
                break
            except Exception:
                time.sleep(0.1)
        if not health or not health.get("ok"):
            raise RuntimeError("health endpoint did not become ready")
        evidence["health"] = health
        evidence["checks"].append("http_health_pass")

        session = request_json(f"http://127.0.0.1:{port}/api/sessions", {"engine": "emulator"})
        evidence["session"] = session
        evidence["checks"].append("session_create_pass")

        uri = f"ws://127.0.0.1:{port}{session['wsPath']}"
        with connect(uri, open_timeout=3, close_timeout=3) as websocket:
            first = json.loads(websocket.recv(timeout=3))
            assert first["type"] == "snapshot"
            assert first["frame"]["frameId"] == 0
            assert first["frame"]["players"][0]["active"]["serial"] == 1001
            assert first["legalSelections"] == [[0]]
            evidence["checks"].append("websocket_initial_snapshot_pass")

            websocket.send(json.dumps({"type": "ping"}))
            pong = json.loads(websocket.recv(timeout=3))
            assert pong["type"] == "pong"
            evidence["checks"].append("websocket_ping_pong_pass")

            frames = [first["frame"]]
            for expected in range(1, 4):
                websocket.send(json.dumps({"type": "step", "selection": [0]}))
                message = json.loads(websocket.recv(timeout=3))
                assert message["type"] == "snapshot"
                assert message["frame"]["frameId"] == expected
                assert message["frame"]["players"][0]["active"]["serial"] == 1001
                assert message["frame"]["players"][1]["active"]["serial"] == 2001
                frames.append(message["frame"])
            evidence["checks"].append("three_live_steps_pass")
            evidence["checks"].append("card_instance_identity_stable")

            websocket.send(json.dumps({"type": "step", "selection": [9]}))
            rejected = json.loads(websocket.recv(timeout=3))
            assert rejected["type"] == "error" and rejected["code"] == "ENGINE_REJECTED"
            evidence["checks"].append("illegal_selection_fail_closed_pass")

            websocket.send(json.dumps({"type": "close"}))
            closed = json.loads(websocket.recv(timeout=3))
            assert closed["type"] == "closed"
            evidence["checks"].append("clean_close_pass")

        with connect(uri, open_timeout=3, close_timeout=3) as websocket:
            resumed = json.loads(websocket.recv(timeout=3))
            assert resumed["frame"]["frameId"] == 3
            assert resumed["frame"]["players"][0]["active"]["serial"] == 1001
            evidence["checks"].append("reconnect_latest_snapshot_pass")

        evidence["frameCount"] = len(frames)
        evidence["verdict"] = "PASS"
        output = ROOT / "connection_smoke_result.json"
        output.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
