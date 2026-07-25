from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parent
RAW_CARD_ID = 987654321
RAW_SERIAL = 123456789


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(url: str, data: dict | None = None) -> dict:
    body = None if data is None else json.dumps(data).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.loads(response.read())


def request_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=3) as response:
        return response.read().decode("utf-8")


def upload_file(url: str, path: Path) -> dict:
    boundary = "----black" + uuid.uuid4().hex
    data = path.read_bytes()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
        "Content-Type: application/gzip\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def make_bundle(path: Path) -> None:
    entries = [
        ("main.py", b"def agent(*args, **kwargs):\n    return []\n"),
        ("deck.csv", ("\n".join(["1"] * 60) + "\n").encode()),
        ("cg/libcg.so", b"\x7fELFprivacy-smoke"),
    ]
    with tarfile.open(path, "w:gz") as archive:
        for name, data in entries:
  info = tarfile.TarInfo(name)
  info.size = len(data)
  archive.addfile(info, io.BytesIO(data))


def make_runner(path: Path) -> None:
    path.write_text("""#!/usr/bin/env python3
import json
import sys

frame_id = 0

def card(player, zone, serial, card_id, name):
    return {"playerIndex": player, "serial": serial, "cardId": card_id, "name": name, "zone": zone, "slot": 0, "hp": 200, "maxHp": 320, "damage": 120, "energies": [44444444], "tools": [55555555], "status": [], "evolution": [], "imageUrl": None}

def frame():
    own = card(0, "active", 123456789, 987654321, "Dragapult ex")
    opp = card(1, "active", 223456789, 887654321, "Rocket Mewtwo ex")
    secret = card(1, "hand", 323456789, 787654321, "Secret Hand")
    return {"frameId": frame_id, "turn": 3, "actionCount": frame_id, "actingPlayer": 0, "phase": "main", "players": [{"name": "/home/user/private/main.py", "active": own, "bench": [], "hand": [own], "handCount": 1, "deckCount": 42, "prizeCount": 5, "discard": [], "supporterPlayed": False, "retreated": False}, {"name": "Opponent", "active": opp, "bench": [], "hand": [secret], "handCount": 4, "deckCount": 39, "prizeCount": 4, "discard": [], "supporterPlayed": False, "retreated": False}], "stadium": None, "events": [{"type": "log", "actor": 0, "text": "selection index=7 /tmp/libcg.so"}], "decision": {"actor": 0, "goal": "searchId=123456789", "chosen": "[7]", "confidence": 0.8, "elapsedMs": 2.0, "candidates": [{"label": "ATTACK", "score": 1.0, "selected": True}], "selectedAction": {"optionIndex": 7}, "hiddenBelief": {"secret": 1}}, "result": None}

for line in sys.stdin:
    message = json.loads(line)
    if message.get("type") == "step":
        if message.get("selection") != [7]:
  print(json.dumps({"type": "error", "detail": "wrong selection /tmp/private serial=123456789"}), flush=True)
  continue
        frame_id += 1
    print(json.dumps({"type": "snapshot", "frame": frame(), "legalSelections": [[7], [8]]}), flush=True)
""", encoding="utf-8")
    path.chmod(0o755)


def assert_session_gone(uri: str) -> None:
    failed = False
    try:
        with connect(uri, open_timeout=2, close_timeout=2) as websocket:
  websocket.recv(timeout=1)
    except Exception:
        failed = True
    assert failed, "closed session remained reconnectable"


def main() -> int:
    port = free_port()
    with tempfile.TemporaryDirectory(prefix="black-privacy-smoke-") as temp:
        temp_path = Path(temp)
        runner = temp_path / "fake_official_runner.py"
        bundle = temp_path / "privacy_bundle.tgz"
        make_runner(runner)
        make_bundle(bundle)
        env = {**os.environ, "BLACK_OFFICIAL_RUNNER": str(runner), "BLACK_BUNDLE_ROOT": str(temp_path / "bundles")}
        command = [sys.executable, "-m", "uvicorn", "live_server:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"]
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
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
  assert health.get("publicView") == "1.1"
  evidence["health"] = health
  evidence["checks"].append("http_health_pass")

  if os.environ.get("EXPECT_FRONTEND_DIST") == "1":
      assert health.get("frontendDist") is True
      assert 'id="root"' in request_text(f"http://127.0.0.1:{port}/")
      evidence["checks"].append("built_pwa_static_serve_pass")

  emulator = request_json(f"http://127.0.0.1:{port}/api/sessions", {"engine": "emulator"})
  evidence["checks"].append("session_create_pass")
  emulator_uri = f"ws://127.0.0.1:{port}{emulator['wsPath']}"
  with connect(emulator_uri, open_timeout=3, close_timeout=3) as websocket:
      first = json.loads(websocket.recv(timeout=3))
      assert first["frame"]["players"][0]["active"]["serial"] == 1001
      assert first["legalSelections"] == [[0]]
      evidence["checks"].append("websocket_initial_snapshot_pass")
      websocket.send(json.dumps({"type": "ping"}))
      assert json.loads(websocket.recv(timeout=3))["type"] == "pong"
      evidence["checks"].append("websocket_ping_pong_pass")
      frames = [first["frame"]]
      for expected in range(1, 4):
          websocket.send(json.dumps({"type": "step", "selection": [0]}))
          message = json.loads(websocket.recv(timeout=3))
          assert message["frame"]["frameId"] == expected
          assert message["frame"]["players"][0]["active"]["serial"] == 1001
          frames.append(message["frame"])
      evidence["checks"].extend(["three_live_steps_pass", "card_instance_identity_stable"])
      websocket.send(json.dumps({"type": "step", "selection": [9]}))
      rejected = json.loads(websocket.recv(timeout=3))
      assert rejected["type"] == "error" and rejected["code"] == "ENGINE_REJECTED"
      evidence["checks"].append("illegal_selection_fail_closed_pass")
      websocket.send(json.dumps({"type": "close"}))
      assert json.loads(websocket.recv(timeout=3))["type"] == "closed"
      evidence["checks"].append("clean_close_pass")
  assert_session_gone(emulator_uri)
  evidence["checks"].append("session_cleanup_pass")

  uploaded = upload_file(f"http://127.0.0.1:{port}/api/bundles", bundle)
  official = request_json(f"http://127.0.0.1:{port}/api/sessions", {"engine": "official", "bundleId": uploaded["bundleId"], "subjectPlayer": 0})
  assert official["engine"] == "official-battle" and official["publicProtocol"] == "1.1"
  evidence["checks"].append("official_public_session_create_pass")
  official_uri = f"ws://127.0.0.1:{port}{official['wsPath']}"
  with connect(official_uri, open_timeout=3, close_timeout=3) as websocket:
      snapshot = json.loads(websocket.recv(timeout=3))
      encoded = json.dumps(snapshot, ensure_ascii=False)
      assert snapshot["publicProtocol"] == "1.1"
      assert snapshot["hiddenInformationPolicy"] == "player_view"
      assert "legalSelections" not in snapshot
      assert snapshot["controls"]["canAdvance"] is True
      assert snapshot["frame"]["players"][1]["hand"] == []
      evidence["checks"].append("official_public_snapshot_pass")
      for secret in (str(RAW_CARD_ID), str(RAW_SERIAL), "/tmp", "/home/user", "selectedAction", "hiddenBelief", "optionIndex", "searchId", "legalSelections"):
          assert secret not in encoded
      evidence["checks"].append("official_raw_identifiers_absent")
      websocket.send(json.dumps({"type": "step", "selection": [7]}))
      hidden = json.loads(websocket.recv(timeout=3))
      assert hidden["type"] == "error" and hidden["code"] == "ACTION_UNAVAILABLE"
      assert "selection" not in json.dumps(hidden).lower()
      evidence["checks"].append("official_step_contract_hidden")
      initial_serial = snapshot["frame"]["players"][0]["active"]["serial"]
      websocket.send(json.dumps({"type": "advance"}))
      advanced = json.loads(websocket.recv(timeout=3))
      assert advanced["frame"]["frameId"] == 1
      assert advanced["frame"]["players"][0]["active"]["serial"] == initial_serial
      assert "legalSelections" not in advanced
      evidence["checks"].append("official_advance_pass")
      websocket.send(json.dumps({"type": "close"}))
      assert json.loads(websocket.recv(timeout=3))["type"] == "closed"
  assert_session_gone(official_uri)
  evidence["checks"].append("official_session_cleanup_pass")

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
