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
import urllib.request
import uuid
from pathlib import Path

from websockets.sync.client import connect


ROOT = Path(__file__).resolve().parent
RAW_CARD_ID = 987654321
RAW_SERIAL = 123456789
HIDDEN_CARD_IDS = (787654321, 687654321, 587654321)
HIDDEN_NAMES = ("Secret Hand", "Secret Deck", "Secret Prize")


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
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            "Content-Type: application/gzip\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
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
    path.write_text(
        '''#!/usr/bin/env python3
import json
import sys

frame_id = 0


def card(player, zone, serial, card_id, name, slot=0):
    board = zone in {"active", "bench"}
    return {
        "playerIndex": player,
        "serial": serial,
        "cardId": card_id,
        "name": name,
        "zone": zone,
        "slot": slot,
        "hp": 200 if board else None,
        "maxHp": 320 if board else None,
        "damage": 120 if board else 0,
        "energies": [44444444] if board else [],
        "tools": [55555555] if board else [],
        "status": [],
        "evolution": [],
        "imageUrl": None,
    }


def frame():
    own = card(0, "active", 123456789, 987654321, "Dragapult ex")
    opponent = card(1, "active", 223456789, 887654321, "Rocket Mewtwo ex")
    secret_hand = card(1, "hand", 323456789, 787654321, "Secret Hand")
    secret_deck = card(1, "deck", 423456789, 687654321, "Secret Deck")
    secret_prize = card(1, "prize", 523456789, 587654321, "Secret Prize")
    return {
        "frameId": frame_id,
        "turn": 3,
        "actionCount": frame_id,
        "actingPlayer": 0,
        "phase": "main",
        "players": [
            {
                "name": "/home/user/private/main.py",
                "active": own,
                "bench": [],
                "hand": [own],
                "handCount": 1,
                "deck": [],
                "deckCount": 42,
                "prize": [],
                "prizeCount": 5,
                "discard": [],
                "supporterPlayed": False,
                "retreated": False,
            },
            {
                "name": "Opponent",
                "active": opponent,
                "bench": [],
                "hand": [secret_hand],
                "handCount": 4,
                "deck": [secret_deck],
                "deckCount": 39,
                "prize": [secret_prize],
                "prizeCount": 4,
                "discard": [],
                "supporterPlayed": False,
                "retreated": False,
            },
        ],
        "stadium": None,
        "events": [{"type": "log", "actor": 0, "text": "selection index=7 /tmp/libcg.so"}],
        "decision": {
            "actor": 0,
            "goal": "searchId=123456789",
            "chosen": "[7]",
            "confidence": 0.8,
            "elapsedMs": 2.0,
            "candidates": [{"label": "ATTACK", "score": 1.0, "selected": True}],
            "selectedAction": {"optionIndex": 7},
            "hiddenBelief": {"secret": 1},
        },
        "result": None,
    }


for line in sys.stdin:
    message = json.loads(line)
    if message.get("type") == "step":
        if message.get("selection") != [7]:
            print(json.dumps({"type": "error", "detail": "wrong selection /tmp/private serial=123456789"}), flush=True)
            continue
        frame_id += 1
    print(json.dumps({"type": "snapshot", "frame": frame(), "legalSelections": [[7], [8]]}), flush=True)
''',
        encoding="utf-8",
    )
    path.chmod(0o755)


def assert_session_gone(uri: str) -> None:
    reconnectable = False
    try:
        with connect(uri, open_timeout=2, close_timeout=2) as websocket:
            websocket.recv(timeout=1)
            reconnectable = True
    except Exception:
        pass
    assert not reconnectable, "closed session remained reconnectable"


def assert_hidden(snapshot: dict) -> None:
    encoded = json.dumps(snapshot, ensure_ascii=False)
    assert snapshot["hiddenInformationPolicy"] == "player_view"
    assert snapshot["frame"]["players"][1]["hand"] == []
    assert snapshot["frame"]["players"][1].get("deck", []) == []
    assert snapshot["frame"]["players"][1].get("prize", []) == []
    for secret in HIDDEN_NAMES:
        assert secret not in encoded
    for raw_id in HIDDEN_CARD_IDS:
        assert str(raw_id) not in encoded


def main() -> int:
    port = free_port()
    with tempfile.TemporaryDirectory(prefix="black-privacy-smoke-") as temp:
        temp_path = Path(temp)
        runner = temp_path / "fake_official_runner.py"
        bundle = temp_path / "privacy_bundle.tgz"
        make_runner(runner)
        make_bundle(bundle)
        env = {
            **os.environ,
            "BLACK_OFFICIAL_RUNNER": str(runner),
            "BLACK_BUNDLE_ROOT": str(temp_path / "bundles"),
            "BLACK_ALLOW_SIMULATOR_VIEW": "1",
        }
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ]
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
            assert health.get("simulatorView") is True
            evidence["health"] = health
            evidence["checks"].extend(["http_health_pass", "simulator_capability_pass"])

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
                assert rejected["type"] == "error"
                assert rejected["code"] == "ENGINE_REJECTED"
                evidence["checks"].append("illegal_selection_fail_closed_pass")

                websocket.send(json.dumps({"type": "close"}))
                assert json.loads(websocket.recv(timeout=3))["type"] == "closed"
                evidence["checks"].append("clean_close_pass")
            assert_session_gone(emulator_uri)
            evidence["checks"].append("session_cleanup_pass")

            uploaded = upload_file(f"http://127.0.0.1:{port}/api/bundles", bundle)
            official = request_json(
                f"http://127.0.0.1:{port}/api/sessions",
                {"engine": "official", "bundleId": uploaded["bundleId"], "subjectPlayer": 0},
            )
            assert official["engine"] == "official-battle"
            assert official["publicProtocol"] == "1.1"
            assert official["simulatorAvailable"] is True
            evidence["checks"].append("official_public_session_create_pass")

            official_uri = f"ws://127.0.0.1:{port}{official['wsPath']}"
            with connect(official_uri, open_timeout=3, close_timeout=3) as websocket:
                snapshot = json.loads(websocket.recv(timeout=3))
                encoded = json.dumps(snapshot, ensure_ascii=False)
                assert snapshot["publicProtocol"] == "1.1"
                assert snapshot["controls"]["canAdvance"] is True
                assert snapshot["controls"]["simulatorAvailable"] is True
                assert snapshot["controls"]["viewMode"] == "player"
                assert "legalSelections" not in snapshot
                assert_hidden(snapshot)
                evidence["checks"].append("official_public_snapshot_pass")

                for secret in (
                    str(RAW_CARD_ID),
                    str(RAW_SERIAL),
                    "/tmp",
                    "/home/user",
                    "selectedAction",
                    "hiddenBelief",
                    "optionIndex",
                    "searchId",
                    "legalSelections",
                ):
                    assert secret not in encoded
                evidence["checks"].append("official_raw_identifiers_absent")

                websocket.send(json.dumps({"type": "set_view_mode", "mode": "simulator"}))
                simulator = json.loads(websocket.recv(timeout=3))
                simulator_encoded = json.dumps(simulator, ensure_ascii=False)
                assert simulator["hiddenInformationPolicy"] == "simulator_full"
                assert simulator["controls"]["viewMode"] == "simulator"
                assert len(simulator["frame"]["players"][1]["hand"]) == 1
                assert len(simulator["frame"]["players"][1]["deck"]) == 1
                assert len(simulator["frame"]["players"][1]["prize"]) == 1
                for secret in HIDDEN_NAMES:
                    assert secret in simulator_encoded
                for raw_id in HIDDEN_CARD_IDS:
                    assert str(raw_id) not in simulator_encoded
                evidence["checks"].append("simulator_full_reveal_pass")

                websocket.send(json.dumps({"type": "set_view_mode", "mode": "player"}))
                hidden_again = json.loads(websocket.recv(timeout=3))
                assert hidden_again["controls"]["viewMode"] == "player"
                assert_hidden(hidden_again)
                evidence["checks"].append("simulator_rehide_pass")

                websocket.send(json.dumps({"type": "step", "selection": [7]}))
                hidden = json.loads(websocket.recv(timeout=3))
                assert hidden["type"] == "error"
                assert hidden["code"] == "ACTION_UNAVAILABLE"
                assert "selection" not in json.dumps(hidden).lower()
                evidence["checks"].append("official_step_contract_hidden")

                initial_serial = snapshot["frame"]["players"][0]["active"]["serial"]
                websocket.send(json.dumps({"type": "advance"}))
                advanced = json.loads(websocket.recv(timeout=3))
                assert advanced["frame"]["frameId"] == 1
                assert advanced["frame"]["players"][0]["active"]["serial"] == initial_serial
                assert "legalSelections" not in advanced
                assert_hidden(advanced)
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
                process.wait(timeout=5)
            if process.returncode not in (0, -15):
                stdout = process.stdout.read() if process.stdout else ""
                stderr = process.stderr.read() if process.stderr else ""
                print(stdout, file=sys.stderr)
                print(stderr, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
